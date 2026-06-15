"""Supplementary tests for validator.py - validate_keys function."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.validator import validate_keys


@pytest.fixture
def validator_keys_file(tmp_data_dir):
    """Create a keys file for validator tests."""
    keys_file = tmp_data_dir / "keys.json"
    keys_data = {
        "keys": {
            "sk-valid-key-1": {
                "key_masked": "sk-valid...ey-1",
                "provider": "openai",
                "status": "valid",
                "checks": [],
                "tests": {},
                "sources": []
            },
            "sk-invalid-key-2": {
                "key_masked": "sk-inva...ey-2",
                "provider": "anthropic",
                "status": "invalid",
                "checks": [],
                "tests": {},
                "sources": []
            },
            "sk-unknown-key-3": {
                "key_masked": "sk-unkn...ey-3",
                "provider": "unknown",
                "status": "unknown",
                "checks": [],
                "tests": {},
                "sources": []
            }
        }
    }
    keys_file.write_text(json.dumps(keys_data, indent=2), encoding="utf-8")
    return keys_file


class TestValidateKeys:
    """Tests for validate_keys function."""

    @pytest.mark.asyncio
    async def test_validate_all_keys(self, tmp_data_dir, validator_keys_file):
        """Validate all keys in file."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir
            )

        assert results["total"] == 3
        assert results["summary"]["valid"]["count"] >= 0

    @pytest.mark.asyncio
    async def test_validate_with_provider_filter(self, tmp_data_dir, validator_keys_file):
        """Filter keys by provider."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                provider_filter="openai"
            )

        assert results["total"] == 1

    @pytest.mark.asyncio
    async def test_validate_with_status_filter(self, tmp_data_dir, validator_keys_file):
        """Filter keys by status."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                status_filter="valid"
            )

        assert results["total"] == 1

    @pytest.mark.asyncio
    async def test_validate_single_key(self, tmp_data_dir, validator_keys_file):
        """Validate a single specific key."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-valid-key-1"
            )

        assert results["total"] == 1

    @pytest.mark.asyncio
    async def test_validate_with_progress_callback(self, tmp_data_dir, validator_keys_file):
        """Progress callback is called."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                progress_callback=progress_callback
            )

        assert len(progress_calls) >= 2
        assert progress_calls[0] == (0, 3)
        assert progress_calls[-1] == (3, 3)

    @pytest.mark.asyncio
    async def test_validate_unknown_provider(self, tmp_data_dir, validator_keys_file):
        """Unknown provider gets error result."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        with patch("key_manager.validator.PROVIDERS", {}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-unknown-key-3"
            )

        assert results["total"] == 1
        assert results["details"][0]["status"] == "error"
