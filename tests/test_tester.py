"""Tests for tester module."""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.tester import run_test

os.environ.setdefault("KEY_MANAGER_SECRET", "test-secret-for-tester")


@pytest.fixture
def test_config(tmp_data_dir):
    """Create a test config."""
    return {
        "storage": {
            "keys_file": str(tmp_data_dir / "keys.json"),
        },
        "encryption": {
            "passphrase": "test-secret-for-tester"
        }
    }
@pytest.fixture
def sample_keys_with_valid(tmp_data_dir, test_config):
    """Create a keys.json with valid keys for testing."""
    from key_manager.storage import KeyStore
    keys_file = tmp_data_dir / "keys.json"
    keys_data = {
        "keys": {
            "sk-test-openai-12345": {
                "key": "sk-test-openai-12345",
                "key_masked": "sk-test...2345",
                "provider": "openai",
                "status": "valid",
                "last_checked": "2024-01-01T00:00:00Z",
                "checks": [],
                "tests": {},
                "sources": [{"file": "test.json"}]
            },
            "sk-test-anthropic-67890": {
                "key": "sk-test-anthropic-67890",
                "key_masked": "sk-test...7890",
                "provider": "anthropic",
                "status": "valid",
                "last_checked": "2024-01-01T00:00:00Z",
                "checks": [],
                "tests": {},
                "sources": [{"file": "test.json"}]
            },
            "sk-invalid-key": {
                "key": "sk-invalid-key",
                "key_masked": "sk-invalid",
                "provider": "openai",
                "status": "invalid",
                "last_checked": "2024-01-01T00:00:00Z",
                "checks": [],
                "tests": {},
                "sources": [{"file": "test.json"}]
            }
        }
    }
    # Use KeyStore to write encrypted data
    store = KeyStore(keys_file, test_config)
    store.save(keys_data)
    return keys_file


@pytest.fixture
def mock_provider_factory():
    """Factory for creating mock providers."""
    def _create(max_tokens=16384, max_concurrency=10, models=None, error=None):
        provider = MagicMock()
        provider.name = "test-provider"
        provider.get_models = AsyncMock(return_value=models or ["gpt-4", "gpt-3.5-turbo"])
        provider.test_token_limit = AsyncMock(return_value=MagicMock(
            max_tokens=max_tokens,
            error=error
        ))
        provider.test_concurrency = AsyncMock(return_value=MagicMock(
            max_concurrency=max_concurrency,
            rpm_limit=None,
            error=error
        ))
        return provider
    return _create


class TestRunTest:
    """Tests for run_test function."""

    async def test_run_test_basic(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Runs test on valid keys."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                token_steps=[4096, 16384],
                concurrency_steps=[1, 5, 10],
                config=test_config
            )

        assert results["total_tested"] == 2  # Only valid keys
        assert len(results["results"]) == 2

    async def test_run_test_skips_invalid(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory):
        """Skips keys with non-valid status."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir
            )

        # Should only test 2 valid keys, not the invalid one
        assert results["total_tested"] == 2
        tested_keys = [r["key_masked"] for r in results["results"]]
        assert "sk-invalid" not in tested_keys

    async def test_run_test_single_key(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory):
        """Tests only the specified key."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345"
            )

        assert results["total_tested"] == 1
        assert results["results"][0]["key_masked"] == "sk-test...2345"

    async def test_run_test_provider_filter(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory):
        """Filters keys by provider."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                provider_filter="openai"
            )

        assert results["total_tested"] == 1
        assert results["results"][0]["provider"] == "openai"

    async def test_run_test_token_test(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Runs token limit test."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory(max_tokens=65536)

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345",
                token_test=True,
                concurrency_test=False,
                token_steps=[4096, 16384, 65536],
                config=test_config
            )

        result = results["results"][0]
        assert result["token_test"]["tested"] is True
        assert result["token_test"]["max_tokens"] == 65536
        assert result["concurrency_test"]["tested"] is False

    async def test_run_test_concurrency_test(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Runs concurrency test."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory(max_concurrency=20)

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345",
                token_test=False,
                concurrency_test=True,
                concurrency_steps=[1, 5, 10, 20],
                config=test_config
            )

        result = results["results"][0]
        assert result["concurrency_test"]["tested"] is True
        assert result["concurrency_test"]["max_concurrency"] == 20
        assert result["token_test"]["tested"] is False

    async def test_run_test_updates_keys_json(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Updates keys.json with test results."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory(max_tokens=32768, max_concurrency=15, models=["gpt-4"])

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345",
                config=test_config
            )

        # Read updated keys file using KeyStore
        from key_manager.storage import KeyStore
        store = KeyStore(sample_keys_with_valid, test_config)
        data = store.load()

        key_data = data["keys"]["sk-test-openai-12345"]
        assert key_data["tests"]["max_tokens"] == 32768
        assert key_data["tests"]["max_concurrency"] == 15
        assert key_data["tests"]["models"] == ["gpt-4"]
        assert key_data["last_tested"] is not None

    async def test_run_test_saves_results(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Saves results to results file."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345",
                config=test_config
            )

        # Check results file exists
        assert Path(results_file).exists()
        with open(results_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        assert "run_at" in results
        assert results["total_tested"] == 1

    async def test_run_test_progress_callback(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Calls progress callback."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory()
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                progress_callback=progress_callback,
                config=test_config
            )

        # Should have initial (0, 2) and final (2, 2) calls
        assert len(progress_calls) >= 2
        assert progress_calls[0] == (0, 2)
        assert progress_calls[-1] == (2, 2)

    async def test_run_test_unknown_provider(self, tmp_data_dir, sample_keys_with_valid, test_config):
        """Handles unknown provider gracefully."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        with patch("key_manager.tester.PROVIDERS", {}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                config=test_config
            )

        # Should still complete, just skip testing
        assert results["total_tested"] == 2

    async def test_run_test_provider_error(self, tmp_data_dir, sample_keys_with_valid, mock_provider_factory, test_config):
        """Handles provider test error gracefully."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        mock_provider = mock_provider_factory(error="API error")
        mock_provider.test_token_limit.side_effect = Exception("Connection failed")

        with patch("key_manager.tester.PROVIDERS", {"openai": mock_provider}):
            results = await run_test(
                keys_file=str(sample_keys_with_valid),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-test-openai-12345",
                config=test_config
            )

        result = results["results"][0]
        assert result["token_test"]["error"] is not None
