"""Tests for provider auto-detection and related endpoints.

Covers:
- detect_provider() with single/multiple candidates
- /api/check/single auto-detection
- /api/balance auto-detection
- /api/models auto-detection
- /api/models/check auto-detection
- base.py get_models() and _probe_model() using get_base_url()
"""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("KEY_MANAGER_SECRET", "test-secret-for-detection")
os.environ.setdefault("KEY_MANAGER_API_KEY", "test-api-key-12345")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_config(tmp_path):
    return {
        "storage": {
            "keys_file": str(tmp_path / "keys.json"),
            "check_results_file": str(tmp_path / "check_results.json"),
            "test_results_file": str(tmp_path / "test_results.json"),
            "logs_dir": str(tmp_path / "logs"),
        },
        "scan": {"directories": [str(tmp_path / "input")]},
        "proxy": "",
        "check": {"concurrency": 10, "timeout_seconds": 10, "retry_failed": False, "retry_count": 0},
        "test": {"token_steps": [1024], "concurrency_steps": [1, 5], "concurrency_timeout_seconds": 30},
        "auth": {"api_key": "test-api-key-12345"},
        "rate_limit": {"requests_per_minute": 0},
    }


def _mock_provider(name="openai", check_valid=True, models=None, balance=100.0):
    """Create a mock provider with configurable behavior."""
    provider = MagicMock()
    provider.name = name
    provider.base_url = f"https://api.{name}.com"
    provider.check_endpoint = "/v1/models" if name == "openai" else "/models"

    provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
    provider.get_base_url.return_value = provider.base_url

    provider.check = AsyncMock(return_value=SimpleNamespace(
        valid=check_valid,
        status_code=200 if check_valid else 401,
        latency_ms=100.0,
        error=None if check_valid else "invalid key",
        error_type=None if check_valid else "invalid_key",
        response_body=None,
    ))

    provider.get_models = AsyncMock(return_value=models or ["gpt-3.5-turbo", "gpt-4"])
    provider.probe = AsyncMock(return_value=SimpleNamespace(
        valid=True,
        status_code=200,
        latency_ms=50.0,
        error=None,
        response_body='{"data": []}',
    ))
    provider._probe_model = AsyncMock(return_value=True)
    provider.get_balance = AsyncMock(return_value=SimpleNamespace(
        supported=True,
        balance=balance,
        currency="USD",
        error=None,
    ))

    return provider


@pytest.fixture
def client(tmp_path):
    cfg = _make_config(tmp_path)
    with patch("key_manager.web.config", cfg):
        from key_manager.web import app
        yield TestClient(app, headers={"Authorization": "Bearer test-api-key-12345"})


# ── detect_provider() Tests ──────────────────────────────────────────────────

class TestDetectProvider:
    """Tests for the detect_provider() function in detector.py."""

    @pytest.mark.asyncio
    async def test_single_candidate_returns_directly(self):
        """When only one candidate matches prefix, return it without probing."""
        from key_manager.detector import detect_by_prefix

        # AIza prefix only matches google
        candidates = detect_by_prefix("AIzaSyExample123")
        assert candidates == ["google"]

    @pytest.mark.asyncio
    async def test_multiple_candidates_uses_check(self):
        """When multiple providers exist, probe all concurrently and return first valid."""
        from key_manager.detector import detect_provider

        mock_openai = _mock_provider("openai", check_valid=False)
        mock_deepseek = _mock_provider("deepseek", check_valid=True, models=["deepseek-chat"])

        # Mock the client.get to return models for both providers
        async def mock_get(url, headers=None):
            provider = "deepseek" if "deepseek" in url else "openai"
            return MagicMock(
                status_code=200,
                json=lambda: {"data": [{"id": f"{provider}-chat"}]}
            )

        # Mock the client.post to return 200 for deepseek, 401 for openai
        async def mock_post(url, headers=None, json=None):
            if "deepseek" in url:
                return MagicMock(status_code=200, text='{"choices": []}')
            return MagicMock(status_code=401, text='{"error": "invalid"}')

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.post = AsyncMock(side_effect=mock_post)

        with patch("key_manager.detector.PROVIDERS", {"openai": mock_openai, "deepseek": mock_deepseek}):
            result = await detect_provider(mock_client, "sk-test123")

        # Should detect deepseek because its request returns 200
        assert result == "deepseek"

    @pytest.mark.asyncio
    async def test_no_candidates_returns_none(self):
        """When no candidates match, return None."""
        from key_manager.detector import detect_provider

        mock_provider = MagicMock()
        mock_provider.check_endpoint = "/v1/models"
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test"}
        mock_provider.get_base_url.return_value = "https://api.test.com"
        mock_provider.check_model = "test-model"

        async def mock_get(*args, **kwargs):
            resp = MagicMock()
            resp.status_code = 401
            resp.json.return_value = {"data": []}
            return resp

        async def mock_post(*args, **kwargs):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "{}"
            return resp

        mock_client = MagicMock()
        mock_client.get = mock_get
        mock_client.post = mock_post

        with patch("key_manager.detector.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.detector.detect_by_prefix", return_value=[]):
                with patch("key_manager.detector.detect_by_pattern", return_value=None):
                    result = await detect_provider(mock_client, "unknown-key")

    @pytest.mark.asyncio
    async def test_no_candidates_returns_none(self):
        """When no candidates match, return None."""
        from key_manager.detector import detect_provider

        # Mock client that always returns 401
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "{}"
        mock_response.json.return_value = {"data": []}
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.post = AsyncMock(return_value=mock_response)

        # Empty PROVIDERS so no providers to probe
        with patch("key_manager.detector.PROVIDERS", {}):
            result = await detect_provider(mock_client, "unknown-key")

        assert result is None
    @pytest.mark.asyncio
    async def test_pattern_match_takes_priority(self):
        """Pattern matching (unique prefixes) takes priority over prefix matching."""
        from key_manager.detector import detect_by_pattern

        # sk-ant-api03- is a unique prefix for anthropic
        result = detect_by_pattern("sk-ant-api03-test123")
        assert result == "anthropic"


# ── /api/check/single Tests ─────────────────────────────────────────────────

class TestCheckSingleAutoDetection:
    """Tests for /api/check/single endpoint auto-detection."""

    def test_with_provider_specified(self, client):
        """When provider is specified, use it directly."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["status"] == "valid"

    def test_without_provider_auto_detects(self, client):
        """When no provider specified, auto-detect using detect_provider()."""
        mock_provider = _mock_provider("deepseek", check_valid=True, models=["deepseek-chat"])

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    # No provider specified
                    "model": None,
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert body["status"] == "valid"

    def test_auto_detect_calls_check(self, client):
        """Auto-detection must call check() to validate the key, not just return success."""
        mock_provider = _mock_provider("deepseek", check_valid=False)  # Key is invalid
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=False, status_code=401, latency_ms=100.0,
            error="invalid key", error_type="invalid_key"
        ))

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    "model": None,
                })

        # Should return invalid, not valid
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "invalid"
        mock_provider.check.assert_called_once()  # check() must be called

    def test_auto_detect_failure_returns_error(self, client):
        """When auto-detection fails, return error."""
        with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="unknown")):
            resp = client.post("/api/check/single", json={
                "key": "unknown-prefix-key",
            })

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"
# ── /api/balance Tests ───────────────────────────────────────────────────────

class TestBalanceAutoDetection:
    """Tests for /api/balance endpoint auto-detection."""

    def test_with_provider_specified(self, client):
        """When provider is specified, use it directly."""
        mock_provider = _mock_provider("deepseek", balance=50.0)

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            resp = client.post("/api/balance", json={
                "key": "sk-test123",
                "provider": "deepseek",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert body["balance"] == 50.0
        assert body["currency"] == "USD"

    def test_without_provider_auto_detects(self, client):
        """When no provider specified, auto-detect using detect_provider()."""
        mock_provider = _mock_provider("deepseek", balance=75.0)

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/balance", json={
                    "key": "sk-test123",
                    # No provider specified
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert body["balance"] == 75.0

    def test_auto_detect_failure_returns_error(self, client):
        """When auto-detection fails, return error."""
        with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="unknown")):
            resp = client.post("/api/balance", json={
                "key": "unknown-prefix-key",
            })

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"


# ── /api/models Tests ────────────────────────────────────────────────────────

class TestModelsAutoDetection:
    """Tests for /api/models endpoint auto-detection."""

    def test_with_provider_specified(self, client):
        """When provider is specified, return its models."""
        mock_provider = _mock_provider("openai", models=["gpt-3.5-turbo", "gpt-4"])

        with patch("key_manager.web.PROVIDERS", {"openai": mock_provider}):
            resp = client.get("/api/models?provider=openai&key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert "gpt-3.5-turbo" in body["models"]

    def test_without_provider_auto_detects(self, client):
        """When no provider specified but key provided, auto-detect."""
        mock_provider = _mock_provider("deepseek", models=["deepseek-chat", "deepseek-coder"])

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.get("/api/models?key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert "deepseek-chat" in body["models"]

    def test_without_key_returns_all_static(self, client):
        """When no key provided, return all static models."""
        resp = client.get("/api/models")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "all"
        assert body["source"] == "static"


# ── base.py get_models() Tests ───────────────────────────────────────────────

class TestBaseProviderGetModels:
    """Tests for ProviderBase.get_models() using get_base_url()."""

    @pytest.mark.asyncio
    async def test_get_models_uses_get_base_url(self):
        """get_models() should use get_base_url() not base_url."""
        from key_manager.providers.base import ProviderBase

        class TestProvider(ProviderBase):
            name = "test"
            base_url = "https://original.example.com"
            check_endpoint = "/models"

            def build_headers(self, key):
                return {"Authorization": f"Bearer {key}"}

            async def check(self, client, key):
                pass

            async def test_token_limit(self, client, key, token_steps):
                pass

            async def test_concurrency(self, client, key, concurrency_steps):
                pass

        provider = TestProvider()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
        mock_client.get = AsyncMock(return_value=mock_response)

        # Set custom base URL
        with patch("key_manager.providers.base.custom_base_url") as mock_ctx:
            mock_ctx.get.return_value = "https://custom.example.com"
            models = await provider.get_models(mock_client, "test-key")

        # Should use custom URL
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args[0][0]
        assert "custom.example.com" in call_args
        assert models == ["model-1", "model-2"]


# ── base.py _probe_model() Tests ─────────────────────────────────────────────

class TestBaseProviderProbeModel:
    """Tests for ProviderBase._probe_model() using get_base_url()."""

    @pytest.mark.asyncio
    async def test_probe_model_uses_get_base_url(self):
        """_probe_model() should use get_base_url() not base_url."""
        from key_manager.providers.base import ProviderBase

        class TestProvider(ProviderBase):
            name = "test"
            base_url = "https://original.example.com"
            check_endpoint = "/models"

            def build_headers(self, key):
                return {"Authorization": f"Bearer {key}"}

            async def check(self, client, key):
                pass

            async def test_token_limit(self, client, key, token_steps):
                pass

            async def test_concurrency(self, client, key, concurrency_steps):
                pass

        provider = TestProvider()
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_response)

        # Set custom base URL
        with patch("key_manager.providers.base.custom_base_url") as mock_ctx:
            mock_ctx.get.return_value = "https://custom.example.com"
            result = await provider._probe_model(mock_client, {}, "test-model")

        # Should use custom URL
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args[0][0]
        assert "custom.example.com" in call_args
        assert result is True


# ── /api/test/single Tests ───────────────────────────────────────────────────

class TestTestSingleAutoDetection:
    """Tests for /api/test/single endpoint auto-detection."""

    def test_without_provider_auto_detects(self, client):
        """When no provider specified, auto-detect using detect_provider()."""
        mock_provider = _mock_provider("deepseek", check_valid=True, models=["deepseek-chat"])

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/test/single", json={
                    "key": "sk-test123",
                    # No provider specified
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"


# ── Regression Tests ─────────────────────────────────────────────────────────

class TestRegression:
    """Regression tests to ensure existing functionality still works."""

    def test_check_single_with_provider_still_works(self, client):
        """Existing behavior: check with specified provider should still work."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-proj-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"

    def test_balance_with_provider_still_works(self, client):
        """Existing behavior: balance with specified provider should still work."""
        mock_provider = _mock_provider("deepseek", balance=100.0)

        with patch("key_manager.web.PROVIDERS", {"deepseek": mock_provider}):
            resp = client.post("/api/balance", json={
                "key": "sk-test123",
                "provider": "deepseek",
            })

        assert resp.status_code == 200
        assert resp.json()["balance"] == 100.0

    def test_models_with_provider_still_works(self, client):
        """Existing behavior: models with specified provider should still work."""
        mock_provider = _mock_provider("openai", models=["gpt-4"])

        with patch("key_manager.web.PROVIDERS", {"openai": mock_provider}):
            resp = client.get("/api/models?provider=openai&key=sk-test123")

        assert resp.status_code == 200
        assert "gpt-4" in resp.json()["models"]
