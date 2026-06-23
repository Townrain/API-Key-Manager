"""Tests for uncovered paths in key_manager/web/routes/check.py.

Covers:
- SSRF validation on custom_base_url
- _check_model_specific error/exception branches
- Auto-save new/existing keys after check
- Batch edge cases (empty keys, auto-detect fallback, unknown provider)
- Error type classification (rate_limited, insufficient_balance)
- Balance/models query exception handling
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from key_manager.errors import ErrorCode, ValidationError
from tests.conftest import make_config, write_keys_file, make_keys_data
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_config, write_keys_file, make_keys_data


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_provider(name="openai", check_valid=True, status_code=200):
    """Create a mock provider with configurable check behavior."""
    provider = MagicMock()
    provider.name = name
    provider.base_url = f"https://api.{name}.com"
    provider.check_endpoint = "/v1/models"
    provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
    provider.get_base_url.return_value = provider.base_url

    sc = status_code if not check_valid else 200
    provider.check = AsyncMock(return_value=SimpleNamespace(
        valid=check_valid,
        status_code=sc,
        latency_ms=100.0,
        error=None if check_valid else f"HTTP {sc}",
        error_type=None,
        response_body=None,
    ))
    provider.get_models = AsyncMock(return_value=["gpt-4"])
    provider.get_balance = AsyncMock(return_value=SimpleNamespace(
        supported=True, balance=100.0, currency="USD", error=None,
    ))
    return provider


# ── SSRF Validation (lines 129-131) ─────────────────────────────────────


class TestSSRFValidation:
    """Tests for custom_base_url SSRF protection in /api/check/single."""

    def test_custom_url_blocked_by_ssrf(self, client):
        """custom_base_url that fails SSRF validation returns 400."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web.routes.check.validate_custom_base_url",
                side_effect=ValidationError(
                    code=ErrorCode.VALIDATION_INVALID_FORMAT,
                    message="Localhost not allowed",
                ),
            ):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    "provider": "openai",
                    "custom_base_url": "http://127.0.0.1:8080",
                })

        assert resp.status_code == 400

    def test_custom_url_allowed_sets_context(self, client):
        """custom_base_url that passes SSRF validation sets context var."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web.routes.check.validate_custom_base_url",
                return_value="https://custom.openai.com",
            ):
                with patch(
                    "key_manager.web.routes.check.custom_base_url"
                ) as mock_ctx:
                    mock_ctx.set = MagicMock()
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123",
                        "provider": "openai",
                        "custom_base_url": "https://custom.openai.com",
                    })

        assert resp.status_code == 200
        # Context should be set and then cleared
        mock_ctx.set.assert_any_call("https://custom.openai.com")
        mock_ctx.set.assert_any_call(None)

    def test_custom_url_cleared_in_finally(self, client):
        """custom_base_url context var is cleared even on exception."""
        mock_provider = _mock_provider("openai", check_valid=True)
        # Make provider.check succeed so we can verify finally cleanup
        # The finally block runs after success too

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web.routes.check.validate_custom_base_url",
                return_value="https://custom.openai.com",
            ):
                with patch(
                    "key_manager.web.routes.check.custom_base_url"
                ) as mock_ctx:
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123",
                        "provider": "openai",
                        "custom_base_url": "https://custom.openai.com",
                    })

        # Context should be set and then cleared in finally block
        mock_ctx.set.assert_any_call("https://custom.openai.com")
        mock_ctx.set.assert_any_call(None)


# ── Missing Key Validation (line 133) ───────────────────────────────────


class TestMissingKeyValidation:
    """Tests for empty key validation."""

    def test_empty_key_returns_error(self, client):
        """Empty key in request returns validation error."""
        resp = client.post("/api/check/single", json={
            "key": "",
            "provider": "openai",
        })

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_whitespace_only_key_returns_error(self, client):
        """Whitespace-only key returns validation error."""
        resp = client.post("/api/check/single", json={
            "key": "   ",
            "provider": "openai",
        })

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"


# ── _check_model_specific (lines 67-74, 180) ────────────────────────────


class TestCheckModelSpecific:
    """Tests for _check_model_specific function."""

    def test_single_check_with_model_calls_model_specific(self, client):
        """When provider and model are specified, _check_model_specific is called."""
        mock_provider = _mock_provider("openai", check_valid=True)
        mock_provider.check_endpoint = "/v1/models"

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web.routes.check._check_model_specific",
                new=AsyncMock(return_value=SimpleNamespace(
                    valid=True, status_code=200, latency_ms=50.0, error=None,
                )),
            ) as mock_cms:
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    "provider": "openai",
                    "model": "gpt-4",
                })

        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"
        mock_cms.assert_called_once()

    def test_model_specific_non_200_returns_error(self, client):
        """_check_model_specific with non-200 response returns error result."""
        mock_provider = _mock_provider("openai", check_valid=True)
        mock_provider.check_endpoint = "/v1/models"
        mock_provider.build_headers.return_value = {"Authorization": "Bearer sk-test"}
        mock_provider.get_base_url.return_value = "https://api.openai.com"

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": {"message": "quota exceeded"}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    "provider": "openai",
                    "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        # 403 is in (401, 403) → status is 'invalid'
        assert body["status"] == "invalid"

    def test_model_specific_exception_returns_error(self, client):
        """_check_model_specific with exception returns error result."""
        mock_provider = _mock_provider("openai", check_valid=True)
        mock_provider.check_endpoint = "/v1/models"
        mock_provider.build_headers.return_value = {"Authorization": "Bearer sk-test"}
        mock_provider.get_base_url.return_value = "https://api.openai.com"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123",
                    "provider": "openai",
                    "model": "gpt-4",
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"


# ── Error Type Classification (lines 209-214) ───────────────────────────


class TestErrorTypeClassification:
    """Tests for error_type assignment based on status code."""

    def test_rate_limited_error_type(self, client):
        """429 status code sets error_type to rate_limited."""
        mock_provider = _mock_provider("openai", check_valid=False, status_code=429)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["error_type"] == "rate_limited"
        assert body["status"] == "error"

    def test_insufficient_balance_error_type(self, client):
        """402 status code sets error_type to insufficient_balance."""
        mock_provider = _mock_provider("openai", check_valid=False, status_code=402)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["error_type"] == "insufficient_balance"

    def test_401_sets_invalid_key_and_status_invalid(self, client):
        """401 status code sets error_type to invalid_key and status to invalid."""
        mock_provider = _mock_provider("openai", check_valid=False, status_code=401)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["error_type"] == "invalid_key"
        assert body["status"] == "invalid"

    def test_other_error_status_code_classified_as_error(self, client):
        """Non-401/402/403/429 status code has no error_type, status=error."""
        mock_provider = _mock_provider("openai", check_valid=False, status_code=500)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["error_type"] is None
        assert body["status"] == "error"


# ── Balance/Models Exception Handling (lines 196-197, 204-205) ──────────


class TestBalanceModelsException:
    """Tests for graceful handling when balance/models queries fail."""

    def test_balance_query_exception_ignored(self, client):
        """Exception from get_balance is silently ignored."""
        mock_provider = _mock_provider("openai", check_valid=True)
        mock_provider.get_balance = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["balance"] is None

    def test_models_query_exception_ignored(self, client):
        """Exception from get_models is silently ignored."""
        mock_provider = _mock_provider("openai", check_valid=True)
        mock_provider.get_models = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/single", json={
                "key": "sk-test123",
                "provider": "openai",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["models"] == []


# ── Auto-save (lines 224-256) ───────────────────────────────────────────


class TestAutoSave:
    """Tests for auto-save of checked keys to registry."""

    def test_auto_save_new_key(self, client):
        """New key is saved to registry after check."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app._load_keys_data",
                return_value={"keys": {}},
            ):
                with patch(
                    "key_manager.web._app._save_keys_data"
                ) as mock_save:
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123456789",
                        "provider": "openai",
                    })

        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"
        # _save_keys_data should be called with the new key in the data
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert "sk-test123456789" in saved_data["keys"]

    def test_auto_save_existing_key_updates_status(self, client):
        """Existing key's status is updated after check."""
        mock_provider = _mock_provider("openai", check_valid=True)

        existing_data = make_keys_data(keys=[
            {"key": "sk-test123456789", "provider": "openai", "status": "unknown"},
        ])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app._load_keys_data",
                return_value=existing_data,
            ):
                with patch(
                    "key_manager.web._app._save_keys_data"
                ) as mock_save:
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123456789",
                        "provider": "openai",
                    })

        assert resp.status_code == 200
        # save should be called (existing key path)
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        key_info = saved_data["keys"]["sk-test123456789"]
        assert key_info["status"] == "valid"
        assert key_info["provider"] == "openai"
        # Should have appended a new check entry
        assert len(key_info["checks"]) > 0

    def test_auto_save_existing_key_without_checks_field(self, client):
        """Existing key without 'checks' field gets empty list initialized."""
        mock_provider = _mock_provider("openai", check_valid=True)

        # Create existing key data WITHOUT a 'checks' field
        existing_data = {"keys": {
            "sk-test123456789": {
                "key": "sk-test123456789",
                "key_masked": "sk-tes...6789",
                "provider": "openai",
                "status": "unknown",
                "last_checked": None,
                "sources": [],
                "tests": {},
                "first_seen": "2024-01-01T00:00:00Z",
                "last_tested": None,
                "created_at": "2024-01-01T00:00:00Z",
            }
        }}

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app._load_keys_data",
                return_value=existing_data,
            ):
                with patch(
                    "key_manager.web._app._save_keys_data"
                ) as mock_save:
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123456789",
                        "provider": "openai",
                    })

        assert resp.status_code == 200
        saved_data = mock_save.call_args[0][0]
        key_info = saved_data["keys"]["sk-test123456789"]
        # 'checks' should be initialized then appended
        assert len(key_info["checks"]) == 1
        assert key_info["checks"][0]["status"] == "valid"

    def test_auto_save_exception_does_not_fail_request(self, client):
        """Exception during auto-save does not fail the check request."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app._load_keys_data",
                side_effect=RuntimeError("disk full"),
            ):
                resp = client.post("/api/check/single", json={
                    "key": "sk-test123456789",
                    "provider": "openai",
                })

        # Request should still succeed
        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"


# ── Batch Edge Cases (lines 278, 294, 303-310, 316, 349-352) ────────────


class TestBatchEdgeCases:
    """Tests for batch check edge cases."""

    def test_batch_empty_keys_returns_error(self, client):
        """Empty keys list returns validation error."""
        resp = client.post("/api/check/batch", json={"keys": []})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_batch_whitespace_key_item_returns_error_result(self, client):
        """Whitespace-only key in batch item returns error result."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/batch", json={
                "keys": [
                    {"key": " ", "provider": "openai"},
                ],
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total"] == 1
        assert body["summary"]["error"] == 1
        assert body["results"][0]["status"] == "error"
        assert body["results"][0]["key_masked"] == "(empty)"

    def test_batch_auto_detect_fallback(self, client):
        """Batch auto-detects provider when not specified."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app.detect_provider",
                new=AsyncMock(return_value="openai"),
            ):
                resp = client.post("/api/check/batch", json={
                    "keys": [
                        {"key": "sk-test123456789"},
                    ],
                })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["valid"] == 1
        assert body["results"][0]["provider"] == "openai"

    def test_batch_unknown_provider_returns_error(self, client):
        """Batch with unknown provider returns error result."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            with patch(
                "key_manager.web._app.detect_provider",
                new=AsyncMock(return_value=None),
            ):
                with patch(
                    "key_manager.web.routes.check.detect_by_prefix",
                    return_value=[],
                ):
                    resp = client.post("/api/check/batch", json={
                        "keys": [
                            {"key": "sk-test123456789"},
                        ],
                    })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["error"] == 1
        assert "Unknown provider" in body["results"][0]["error"]

    def test_batch_summary_counts_invalid(self, client):
        """Batch summary correctly counts invalid keys."""
        mock_provider = _mock_provider("openai", check_valid=False, status_code=401)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/batch", json={
                "keys": [
                    {"key": "sk-test123456789", "provider": "openai"},
                ],
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["invalid"] == 1
        assert body["summary"]["valid"] == 0
        assert body["summary"]["error"] == 0

    def test_batch_mixed_statuses(self, client):
        """Batch summary correctly counts mixed valid/invalid/error statuses."""
        results = [
            SimpleNamespace(valid=True, status_code=200, latency_ms=50.0, error=None, error_type=None),
            SimpleNamespace(valid=False, status_code=401, latency_ms=50.0, error="invalid", error_type="invalid_key"),
            SimpleNamespace(valid=False, status_code=500, latency_ms=50.0, error="server error", error_type=None),
        ]
        results_iter = iter(results)

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(side_effect=lambda c, k: next(results_iter))
        mock_provider.base_url = "https://api.openai.com"

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/batch", json={
                "keys": [
                    {"key": "sk-valid12345678", "provider": "openai"},
                    {"key": "sk-invalid1234567", "provider": "openai"},
                    {"key": "sk-error123456789", "provider": "openai"},
                ],
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total"] == 3
        assert body["summary"]["valid"] == 1
        assert body["summary"]["invalid"] == 1
        assert body["summary"]["error"] == 1


class TestAutoDetectWithModel:
    """Tests for auto-detected provider with model specified (lines 185-186)."""

    def test_auto_detected_provider_with_model(self, client):
        """When provider is auto-detected and model is specified, _check_model_specific is called."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app.detect_provider",
                new=AsyncMock(return_value="openai"),
            ):
                with patch(
                    "key_manager.web.routes.check._check_model_specific",
                    new=AsyncMock(return_value=SimpleNamespace(
                        valid=True, status_code=200, latency_ms=50.0, error=None,
                    )),
                ) as mock_cms:
                    resp = client.post("/api/check/single", json={
                        "key": "sk-test123",
                        "model": "gpt-4",
                    })

        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"
        mock_cms.assert_called_once()

    def test_batch_auto_detect_exception_falls_back_to_prefix(self, client):
        """When detect_provider raises in batch, falls back to prefix detection."""
        mock_provider = _mock_provider("openai", check_valid=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch(
                "key_manager.web._app.detect_provider",
                new=AsyncMock(side_effect=RuntimeError("timeout")),
            ):
                with patch(
                    "key_manager.web.routes.check.detect_by_prefix",
                    return_value=["openai"],
                ):
                    resp = client.post("/api/check/batch", json={
                        "keys": [
                            {"key": "sk-proj-test12345"},
                        ],
                    })

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["valid"] == 1
        assert body["results"][0]["provider"] == "openai"
