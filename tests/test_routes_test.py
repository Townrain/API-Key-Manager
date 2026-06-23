"""Tests for key_manager/web/routes/test.py — all 6 endpoints.

Endpoints:
  POST /api/test                 — batch token+concurrency test (async)
  POST /api/test/single          — single key test
  POST /api/test/token           — batch token test (async)
  POST /api/test/token/batch     — alias for token test
  POST /api/test/concurrency     — batch concurrency test (async)
  POST /api/test/concurrency/batch — alias for concurrency test
  POST /api/test/concurrency/model — concurrency test for a specific model
  POST /api/test/token/model       — token test for a specific model
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_config, write_keys_file, make_keys_data


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_provider(name="openai", models=None):
    """Create a mock provider for test route testing."""
    provider = MagicMock()
    provider.name = name
    provider.base_url = f"https://api.{name}.com"
    provider.check_endpoint = "/v1/models"
    provider.build_headers.return_value = {"Authorization": "Bearer test"}
    provider.get_base_url.return_value = provider.base_url
    provider.test_token_limit = AsyncMock(return_value=SimpleNamespace(
        max_tokens=16384, models=models or ["gpt-4"], error=None,
    ))
    provider.test_concurrency = AsyncMock(return_value=SimpleNamespace(
        max_concurrency=10, error=None,
    ))
    provider.get_models = AsyncMock(return_value=models or ["gpt-4"])
    return provider


# ── POST /api/test ───────────────────────────────────────────────────────────


class TestApiTest:
    """Tests for POST /api/test — batch token+concurrency test."""

    def test_returns_loading_status(self, client):
        """Endpoint returns immediately with loading status."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={"total_tested": 2})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Test started"
        assert body["status"] == "loading"

    def test_calls_progress_tracker_start(self, client):
        """Progress tracker start() is called before task creation."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test")

        mock_tracker.start.assert_called_once_with(total=0, status="loading")


# ── POST /api/test/single ────────────────────────────────────────────────────


class TestApiTestSingle:
    """Tests for POST /api/test/single — single key test."""

    def test_with_provider_success(self, client):
        """Test single key with explicit provider returns full results."""
        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["max_tokens"] == 16384
        assert body["max_concurrency"] == 10
        assert "gpt-4" in body["models"]

    def test_empty_key_raises_validation_error(self, client):
        """Empty key raises VALIDATION_MISSING_KEY."""
        resp = client.post("/api/test/single", json={
            "key": "", "provider": "openai",
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_whitespace_key_raises_validation_error(self, client):
        """Whitespace-only key raises VALIDATION_MISSING_KEY."""
        resp = client.post("/api/test/single", json={
            "key": "   ", "provider": "openai",
        })
        assert resp.status_code == 400

    def test_auto_detect_provider_success(self, client):
        """When no provider specified, auto-detect and use detected provider."""
        mock_prov = _mock_provider("deepseek")
        with patch("key_manager.web._app.PROVIDERS", {"deepseek": mock_prov}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/test/single", json={
                    "key": "sk-test123",
                })

        assert resp.status_code == 200
        assert resp.json()["provider"] == "deepseek"

    def test_auto_detect_returns_unknown_raises_error(self, client):
        """When auto-detect returns 'unknown', raise VALIDATION_PROVIDER_UNKNOWN."""
        with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="unknown")):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123",
            })

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_auto_detect_returns_none_raises_error(self, client):
        """When auto-detect returns None, raise VALIDATION_PROVIDER_UNKNOWN."""
        with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value=None)):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123",
            })

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_unknown_provider_raises_error(self, client):
        """Unknown provider name raises VALIDATION_PROVIDER_UNKNOWN."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "nonexistent",
            })

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_token_test_error_is_reported(self, client):
        """When token test returns an error field, it's included in response."""
        mock_prov = _mock_provider("openai")
        mock_prov.test_token_limit = AsyncMock(return_value=SimpleNamespace(
            max_tokens=None, models=["gpt-4"], error="rate limited",
        ))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        assert resp.json()["error"] == "rate limited"

    def test_token_test_exception_is_captured(self, client):
        """When token test raises, the exception is captured as error."""
        mock_prov = _mock_provider("openai")
        mock_prov.test_token_limit = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        assert "boom" in resp.json()["error"]

    def test_concurrency_test_error_is_reported(self, client):
        """When concurrency test returns error and no prior error, it's used."""
        mock_prov = _mock_provider("openai")
        mock_prov.test_token_limit = AsyncMock(return_value=SimpleNamespace(
            max_tokens=16384, models=["gpt-4"], error=None,
        ))
        mock_prov.test_concurrency = AsyncMock(return_value=SimpleNamespace(
            max_concurrency=0, error="connection refused",
        ))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        assert resp.json()["error"] == "connection refused"

    def test_concurrency_test_exception_is_captured(self, client):
        """When concurrency test raises, the exception is captured."""
        mock_prov = _mock_provider("openai")
        mock_prov.test_token_limit = AsyncMock(return_value=SimpleNamespace(
            max_tokens=16384, models=["gpt-4"], error=None,
        ))
        mock_prov.test_concurrency = AsyncMock(side_effect=RuntimeError("timeout"))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        assert "timeout" in resp.json()["error"]

    def test_get_models_exception_is_ignored(self, client):
        """When get_models raises, models list stays empty."""
        mock_prov = _mock_provider("openai")
        mock_prov.get_models = AsyncMock(side_effect=RuntimeError("fail"))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.status_code == 200
        assert resp.json()["models"] == []

    def test_concurrency_error_does_not_override_token_error(self, client):
        """Concurrency error is not used when a token error already exists."""
        mock_prov = _mock_provider("openai")
        mock_prov.test_token_limit = AsyncMock(return_value=SimpleNamespace(
            max_tokens=None, models=["gpt-4"], error="token error",
        ))
        mock_prov.test_concurrency = AsyncMock(return_value=SimpleNamespace(
            max_concurrency=0, error="concurrency error",
        ))
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "openai",
            })

        assert resp.json()["error"] == "token error"

    def test_provider_name_is_lowered_for_lookup(self, client):
        """Provider name is case-insensitive for lookup; response keeps original case."""
        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            resp = client.post("/api/test/single", json={
                "key": "sk-test123", "provider": "OpenAI",
            })

        assert resp.status_code == 200
        # Response uses the original provider name from request
        assert resp.json()["provider"] == "OpenAI"


# ── POST /api/test/token ─────────────────────────────────────────────────────


class TestApiTestToken:
    """Tests for POST /api/test/token — batch token test."""

    def test_returns_loading_status(self, client):
        """Endpoint returns immediately with loading status."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test/token")

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Token test started"
        assert body["status"] == "loading"

    def test_calls_progress_tracker_start(self, client):
        """Progress tracker start() is called."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test/token")

        mock_tracker.start.assert_called_once_with(total=0, status="loading")


# ── POST /api/test/token/batch ────────────────────────────────────────────────


class TestApiTestTokenBatch:
    """Tests for POST /api/test/token/batch — alias for token test."""

    def test_returns_loading_status(self, client):
        """Batch alias returns same response as token test."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker"):
                resp = client.post("/api/test/token/batch")

        assert resp.status_code == 200
        assert resp.json()["message"] == "Token test started"


# ── POST /api/test/concurrency ───────────────────────────────────────────────


class TestApiTestConcurrency:
    """Tests for POST /api/test/concurrency — batch concurrency test."""

    def test_returns_loading_status(self, client):
        """Endpoint returns immediately with loading status."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test/concurrency")

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Concurrency test started"
        assert body["status"] == "loading"

    def test_calls_progress_tracker_start(self, client):
        """Progress tracker start() is called."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker") as mock_tracker:
                resp = client.post("/api/test/concurrency")

        mock_tracker.start.assert_called_once_with(total=0, status="loading")


# ── POST /api/test/concurrency/batch ──────────────────────────────────────────


class TestApiTestConcurrencyBatch:
    """Tests for POST /api/test/concurrency/batch — alias."""

    def test_returns_loading_status(self, client):
        """Batch alias returns same response as concurrency test."""
        with patch("key_manager.web.routes.test.run_test", new=AsyncMock(return_value={})):
            with patch("key_manager.web.routes.test._progress_tracker"):
                resp = client.post("/api/test/concurrency/batch")

        assert resp.status_code == 200
        assert resp.json()["message"] == "Concurrency test started"


# ── POST /api/test/concurrency/model ─────────────────────────────────────────


class TestApiTestConcurrencyModel:
    """Tests for POST /api/test/concurrency/model."""

    def test_invalid_json_body(self, client):
        """Invalid JSON body raises VALIDATION_INVALID_FORMAT."""
        resp = client.post(
            "/api/test/concurrency/model",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_missing_key_raises_error(self, client):
        """Missing key raises VALIDATION_MISSING_KEY."""
        resp = client.post("/api/test/concurrency/model", json={
            "provider": "openai", "model": "gpt-4", "concurrency": 5,
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_with_provider_all_success(self, client):
        """All probes succeed → max_concurrency == concurrency."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 3,
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_concurrency"] == 3
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4"
        assert body["error"] is None

    def test_with_provider_partial_success(self, client):
        """Partial success → max_concurrency = number of successes."""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return MagicMock(status_code=200)
            return MagicMock(
                status_code=429,
                json=lambda: {"error": {"message": "rate limited"}},
                text="rate limited",
            )

        mock_client = MagicMock()
        mock_client.post = mock_post

        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 3,
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_concurrency"] == 2
        assert body["error"] is None

    def test_with_provider_all_fail(self, client):
        """All probes fail → max_concurrency == 0."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=MagicMock(
            status_code=401,
            json=lambda: {"error": {"message": "invalid key"}},
            text="invalid key",
        ))

        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 3,
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_concurrency"] == 0
        assert body["error"] is not None

    def test_probe_exception_returns_error(self, client):
        """When probe raises, result is captured as error."""

        async def mock_post(*args, **kwargs):
            raise ConnectionError("connection refused")

        mock_client = MagicMock()
        mock_client.post = mock_post

        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 2,
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_concurrency"] == 0

    def test_auto_detect_provider(self, client):
        """When no provider specified, auto-detect is used."""
        mock_prov = _mock_provider("deepseek")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"deepseek": mock_prov}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="deepseek")):
                with patch("httpx.AsyncClient") as mock_http:
                    mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                    resp = client.post("/api/test/concurrency/model", json={
                        "key": "sk-test", "model": "gpt-4", "concurrency": 2,
                    })

        assert resp.status_code == 200
        assert resp.json()["provider"] == "deepseek"

    def test_unknown_provider_raises_error(self, client):
        """Unknown provider raises VALIDATION_PROVIDER_UNKNOWN."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.post("/api/test/concurrency/model", json={
                "key": "sk-test", "provider": "nonexistent",
                "model": "gpt-4", "concurrency": 5,
            })

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_no_model_finds_free_model(self, client):
        """When no model specified, free model is preferred."""
        mock_prov = _mock_provider("openai", models=["gpt-4", "deepseek-free-v2"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai", "concurrency": 2,
                })

        assert resp.status_code == 200
        assert resp.json()["model"] == "deepseek-free-v2"

    def test_no_model_uses_first_model(self, client):
        """When no model and no free model, first model is used."""
        mock_prov = _mock_provider("openai", models=["gpt-4", "gpt-3.5-turbo"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai", "concurrency": 2,
                })

        assert resp.status_code == 200
        assert resp.json()["model"] == "gpt-4"

    def test_no_models_available(self, client):
        """When get_models returns empty list, returns error."""
        mock_prov = _mock_provider("openai", models=[])
        mock_prov.get_models = AsyncMock(return_value=[])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai", "concurrency": 2,
                })

        assert resp.status_code == 200
        assert resp.json()["error"] == "No models available"

    def test_outer_exception_returns_error(self, client):
        """Outer exception is caught and returned as error dict."""
        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient", side_effect=RuntimeError("network down")):
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 2,
                })

        assert resp.status_code == 200
        assert "network down" in resp.json()["error"]

    def test_error_response_without_error_key(self, client):
        """Error response without 'error' key uses status code message."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=MagicMock(
            status_code=500,
            json=lambda: {"message": "internal error"},
            text="internal error",
        ))

        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/concurrency/model", json={
                    "key": "sk-test", "provider": "openai",
                    "model": "gpt-4", "concurrency": 2,
                })

        assert resp.status_code == 200
        assert resp.json()["max_concurrency"] == 0


# ── POST /api/test/token/model ───────────────────────────────────────────────


class TestApiTestTokenModel:
    """Tests for POST /api/test/token/model."""

    def test_invalid_json_body(self, client):
        """Invalid JSON body raises VALIDATION_INVALID_FORMAT."""
        resp = client.post(
            "/api/test/token/model",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_missing_key_raises_error(self, client):
        """Missing key raises VALIDATION_MISSING_KEY."""
        resp = client.post("/api/test/token/model", json={
            "provider": "openai", "model": "gpt-4",
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_missing_model_raises_error(self, client):
        """Missing model raises VALIDATION_MISSING_KEY."""
        resp = client.post("/api/test/token/model", json={
            "key": "sk-test", "provider": "openai",
        })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_unknown_provider_raises_error(self, client):
        """Unknown provider raises VALIDATION_PROVIDER_UNKNOWN."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.post("/api/test/token/model", json={
                "key": "sk-test", "provider": "nonexistent", "model": "gpt-4",
            })

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_200_response_returns_large_tokens(self, client):
        """When API returns 200, max_tokens is the large value sent."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] == 1000000
        assert body["error"] is None

    def test_error_with_maximum_is_N(self, client):
        """Error message 'maximum is 16384' is parsed correctly."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "This model's maximum is 16384 tokens"},
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] == 16384
        assert body["error"] is None

    def test_error_with_numbers_fallback(self, client):
        """Error with multiple numbers (no max/maximum keyword) uses largest >= 100."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "Token limit exceeded. Allowed 8192. You sent 99999."},
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        # Numbers are {8192, 99999}, sorted desc -> first >= 100 is 99999
        assert body["max_tokens"] == 99999
        assert body["error"] is None

    def test_error_with_single_number(self, client):
        """Error with one number >= 100 returns it as max_tokens."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "Limit is 4096"},
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] == 4096
        assert body["error"] is None

    def test_parse_failure_returns_error(self, client):
        """When no limit can be parsed, returns error message."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "something went wrong"},
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] is None
        assert body["error"] == "Could not parse token limit"

    def test_outer_exception_returns_error(self, client):
        """Outer exception is caught and returned as error dict."""
        mock_prov = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient", side_effect=RuntimeError("network error")):
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        assert "network error" in resp.json()["error"]

    def test_auto_detect_provider(self, client):
        """When no provider specified, auto-detect is used."""
        mock_prov = _mock_provider("deepseek")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"deepseek": mock_prov}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="deepseek")):
                with patch("httpx.AsyncClient") as mock_http:
                    mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                    resp = client.post("/api/test/token/model", json={
                        "key": "sk-test", "model": "gpt-4",
                    })

        assert resp.status_code == 200
        assert resp.json()["provider"] == "deepseek"

    def test_json_parse_exception_ignored(self, client):
        """When error_data.json() raises, falls through to parse failure."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "plain text error"
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] is None
        assert body["error"] == "Could not parse token limit"

    def test_small_number_below_100_ignored(self, client):
        """Numbers < 100 are not returned as token limits."""
        mock_prov = _mock_provider("openai")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "request too large, limit 50 tokens"},
        }
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_prov}):
            with patch("httpx.AsyncClient") as mock_http:
                mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post("/api/test/token/model", json={
                    "key": "sk-test", "provider": "openai", "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["max_tokens"] is None
        assert body["error"] == "Could not parse token limit"
