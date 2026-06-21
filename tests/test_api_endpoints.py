"""Tests for API endpoints - comprehensive coverage."""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_config, write_keys_file, make_keys_data



@pytest.fixture
def keys_file(tmp_path):
    """Create a keys file with test data."""
    keys_data = make_keys_data(keys=[
        {"key": "sk-test-openai-12345", "provider": "openai", "status": "valid",
         "last_checked": "2024-01-01T00:00:00Z",
         "tests": {"max_tokens": 16384, "max_concurrency": 10},
         "balance": 100.0},
        {"key": "sk-test-anthropic-67890", "provider": "anthropic", "status": "invalid",
         "last_checked": "2024-01-01T00:00:00Z"},
    ])
    keys_path = Path(make_config(tmp_path)["storage"]["keys_file"])
    write_keys_file(keys_path, keys_data)
    return keys_path


# =============================================================================
# Query Endpoints (GET)
# =============================================================================

class TestProvidersEndpoints:
    """Tests for /api/providers endpoints."""

    def test_list_providers(self, client):
        """GET /api/providers returns provider list."""
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert "providers" in body
        assert "total" in body
        assert body["total"] > 0
        # Check structure
        provider = body["providers"][0]
        assert "name" in provider
        assert "display_name" in provider
        assert "prefix" in provider
        assert "base_url" in provider

    def test_providers_detail(self, client):
        """GET /api/providers/detail returns detailed provider info."""
        resp = client.get("/api/providers/detail")
        assert resp.status_code == 200
        body = resp.json()
        assert "providers" in body
        assert body["total"] > 0
        provider = body["providers"][0]
        assert "website_url" in provider
        assert "docs_url" in provider


class TestStatsEndpoints:
    """Tests for /api/stats endpoints."""

    def test_stats_empty(self, client):
        """GET /api/stats returns empty stats when no keys."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "providers" in body
        assert "total" in body

    def test_stats_with_keys(self, client, keys_file):
        """GET /api/stats returns stats for stored keys."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert "openai" in body["providers"]
        assert "anthropic" in body["providers"]
        assert body["providers"]["openai"]["valid"] == 1
        assert body["providers"]["anthropic"]["invalid"] == 1

    def test_stats_chart_bug(self, client, keys_file):
        """GET /api/stats/chart returns chart data."""
        resp = client.get("/api/stats/chart")
        assert resp.status_code == 200
        body = resp.json()
        assert "providers" in body
        assert "statuses" in body
        # Should have providers for our test keys
        provider_names = [p["provider"] for p in body["providers"]]
        assert "openai" in provider_names
        assert "anthropic" in provider_names
        # Check statuses
        assert body["statuses"]["valid"] == 1
        assert body["statuses"]["invalid"] == 1

class TestProxyEndpoint:
    """Tests for /api/proxy endpoint."""

    def test_proxy_no_config(self, client):
        """GET /api/proxy returns proxy status."""
        resp = client.get("/api/proxy")
        assert resp.status_code == 200
        body = resp.json()
        assert "proxy" in body
        assert "source" in body


class TestLogsEndpoints:
    """Tests for /api/logs endpoints."""

    def test_logs_empty(self, client):
        """GET /api/logs returns empty when no logs."""
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        body = resp.json()
        assert "logs" in body

    def test_logs_operations_empty(self, client):
        """GET /api/logs/operations returns empty when no operations."""
        resp = client.get("/api/logs/operations")
        assert resp.status_code == 200
        body = resp.json()
        assert "operations" in body


class TestProgressEndpoints:
    """Tests for /api/progress endpoints."""

    def test_progress_status(self, client):
        """GET /api/progress returns progress status."""
        resp = client.get("/api/progress")
        assert resp.status_code == 200
        body = resp.json()
        assert "active" in body
        assert "current" in body
        assert "total" in body
        assert "status" in body


# =============================================================================
# Test Endpoints (POST)
# =============================================================================

class TestCheckBatchEndpoint:
    """Tests for /api/check/batch endpoint."""

    def test_check_batch_empty_keys(self, client):
        """POST /api/check/batch with empty keys returns error."""
        resp = client.post("/api/check/batch", json={"keys": []})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_check_batch_valid_keys(self, client):
        """POST /api/check/batch with valid keys."""
        mock_result = MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None
        )
        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=mock_result)

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/check/batch", json={
                "keys": [
                    {"key": "sk-test-12345", "provider": "openai"}
                ]
            })
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert "summary" in body
        assert body["summary"]["total"] == 1


class TestTestEndpoints:
    """Tests for /api/test endpoints."""

    def test_test_single_missing_key(self, client):
        """POST /api/test/single with missing key returns error."""
        resp = client.post("/api/test/single", json={"key": "", "provider": "openai"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_test_single_unknown_provider(self, client):
        """POST /api/test/single with unknown provider returns error."""
        resp = client.post("/api/test/single", json={"key": "sk-test", "provider": "nonexistent"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_test_single_valid(self, client):
        """POST /api/test/single with valid key."""
        mock_provider = MagicMock()
        mock_provider.test_token_limit = AsyncMock(return_value=MagicMock(max_tokens=16384, error=None))
        mock_provider.test_concurrency = AsyncMock(return_value=MagicMock(max_concurrency=10, error=None))
        mock_provider.get_models = AsyncMock(return_value=["gpt-4"])

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/test/single", json={"key": "sk-test-12345", "provider": "openai"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["max_tokens"] == 16384
        assert body["max_concurrency"] == 10

    def test_test_async(self, client):
        """POST /api/test starts async test."""
        resp = client.post("/api/test", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Test started"
        assert body["status"] == "loading"


class TestModelEndpoints:
    """Tests for /api/models endpoints."""

    def test_models_no_provider(self, client):
        """GET /api/models without provider returns all models."""
        resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert "models" in body
        assert "total" in body

    def test_models_with_provider(self, client):
        """GET /api/models with provider returns provider models."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])
        mock_provider.models = ["gpt-4", "gpt-3.5-turbo"]

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.get("/api/models?provider=openai")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"

    def test_models_unknown_provider(self, client):
        """GET /api/models with unknown provider returns empty."""
        resp = client.get("/api/models?provider=nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["models"] == []
        assert body["total"] == 0

    def test_models_with_provider_no_key(self, client):
        """GET /api/models with provider but no key returns static models from PROVIDER_MODELS."""
        resp = client.get("/api/models?provider=openai")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["source"] == "static"
        # Should have models from PROVIDER_MODELS
        assert body["total"] > 0
        assert len(body["models"]) > 0

class TestBalanceEndpoint:
    """Tests for /api/balance endpoint."""

    def test_balance_missing_key(self, client):
        """POST /api/balance with missing key returns error."""
        resp = client.post("/api/balance", json={"key": "", "provider": "openai"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_balance_valid(self, client):
        """POST /api/balance with valid key."""
        mock_provider = MagicMock()
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=True, balance=100.0, currency="USD", error=None
        ))

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/balance", json={"key": "sk-test-12345", "provider": "openai"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["supported"] is True
        assert body["balance"] == 100.0
        assert body["currency"] == "USD"

    def test_balance_unsupported_provider(self, client):
        """POST /api/balance with provider that doesn't support balance."""
        mock_provider = MagicMock(spec=[])  # No get_balance method

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/balance", json={"key": "sk-test-12345", "provider": "openai"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["supported"] is False


# =============================================================================
# Webhook Endpoints
# =============================================================================

class TestWebhookEndpoints:
    """Tests for /api/webhooks endpoints."""

    def test_list_webhooks_empty(self, client):
        """GET /api/webhooks returns empty dict when no webhooks."""
        resp = client.get("/api/webhooks")
        assert resp.status_code == 200
        body = resp.json()
        # Returns raw dict from webhook_manager.list_all()
        assert isinstance(body, dict)
        assert len(body) == 0
    def test_create_webhook(self, client):
        """POST /api/webhooks creates a webhook."""
        resp = client.post("/api/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["key.imported", "key.checked"],
            "active": True
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "webhook_id" in body

    def test_create_webhook_and_list(self, client):
        """Create webhook then list shows it."""
        # Create
        resp = client.post("/api/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["key.imported"],
        })
        webhook_id = resp.json()["webhook_id"]

        # List - returns raw dict keyed by webhook_id
        resp = client.get("/api/webhooks")
        body = resp.json()
        assert webhook_id in body
    def test_get_webhook(self, client):
        """GET /api/webhooks/{id} returns webhook details."""
        # Create
        resp = client.post("/api/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["key.imported"],
        })
        webhook_id = resp.json()["webhook_id"]

        # Get
        resp = client.get(f"/api/webhooks/{webhook_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["url"] == "https://example.com/webhook"

    def test_get_webhook_not_found(self, client):
        """GET /api/webhooks/{id} with invalid ID returns 404."""
        resp = client.get("/api/webhooks/nonexistent")
        assert resp.status_code == 404

    def test_update_webhook(self, client):
        """PUT /api/webhooks/{id} updates webhook."""
        # Create
        resp = client.post("/api/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["key.imported"],
        })
        webhook_id = resp.json()["webhook_id"]

        # Update
        resp = client.put(f"/api/webhooks/{webhook_id}", json={
            "url": "https://updated.com/webhook",
            "active": False
        })
        assert resp.status_code == 200

        # Verify
        resp = client.get(f"/api/webhooks/{webhook_id}")
        assert resp.json()["url"] == "https://updated.com/webhook"

    def test_delete_webhook(self, client):
        """DELETE /api/webhooks/{id} deletes webhook."""
        # Create
        resp = client.post("/api/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["key.imported"],
        })
        webhook_id = resp.json()["webhook_id"]

        # Delete
        resp = client.delete(f"/api/webhooks/{webhook_id}")
        assert resp.status_code == 200

        # Verify deleted
        resp = client.get("/api/webhooks")
        body = resp.json()
        assert webhook_id not in body
    def test_webhook_delivery_log_empty(self, client):
        """GET /api/webhooks/log/deliveries returns empty list."""
        resp = client.get("/api/webhooks/log/deliveries")
        assert resp.status_code == 200
        body = resp.json()
        # Returns raw list from webhook_manager.get_delivery_log()
        assert isinstance(body, list)
        assert len(body) == 0
    def test_clear_delivery_log(self, client):
        """DELETE /api/webhooks/log/deliveries clears log."""
        resp = client.delete("/api/webhooks/log/deliveries")
        assert resp.status_code == 200


# =============================================================================
# Upload Endpoint
# =============================================================================

class TestUploadEndpoint:
    """Tests for /api/import/upload endpoint."""

    def test_upload_no_file(self, client):
        """POST /api/import/upload without file returns error."""
        resp = client.post("/api/import/upload")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_FILE_NOT_FOUND"

    def test_upload_invalid_extension(self, client):
        """POST /api/import/upload with non-JSON file returns error."""
        from io import BytesIO
        resp = client.post(
            "/api/import/upload",
            files={"file": ("test.txt", BytesIO(b"not json"), "text/plain")}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_FILE_FORMAT"

    def test_upload_invalid_json(self, client):
        """POST /api/import/upload with invalid JSON returns error."""
        from io import BytesIO
        resp = client.post(
            "/api/import/upload",
            files={"file": ("test.json", BytesIO(b"not json"), "application/json")}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_FILE_FORMAT"

    def test_upload_valid_json(self, client, tmp_path):
        """POST /api/import/upload with valid JSON imports keys."""
        from io import BytesIO
        keys_data = [{"key": "sk-new-key-12345", "provider": "openai"}]
        json_bytes = json.dumps(keys_data).encode("utf-8")

        with patch("key_manager.parser.import_keys", return_value=(1, 0, [])), \
             patch("key_manager.parser.validate_import_path", side_effect=lambda p, d: Path(p)):
            resp = client.post(
                "/api/import/upload",
                files={"file": ("test.json", BytesIO(json_bytes), "application/json")}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["new"] == 1


# ---------------------------------------------------------------------------
# Test check/single with specific model and auto-detected provider
# ---------------------------------------------------------------------------
class TestCheckSingleSpecificModel:
    """Test /api/check/single with specific model when provider is auto-detected."""

    def test_check_single_with_model_auto_detected(self, client):
        """When provider is auto-detected and model is specified, should test only that model."""
        from unittest.mock import AsyncMock, MagicMock, patch
        
        # Mock detect_provider to return a provider name
        mock_detect = AsyncMock(return_value="deepseek")
        
        # Mock the provider
        mock_provider = MagicMock()
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
        mock_provider.get_base_url.return_value = "https://api.deepseek.com/v1"
        mock_provider.check_endpoint = "/models"
        mock_provider.check = AsyncMock(return_value=MagicMock(valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(supported=False))
        mock_provider.get_models = AsyncMock(return_value=["model-1", "model-2"])
        
        # Mock httpx.AsyncClient.post to return 200
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "hi"}}]}
        
        with patch("key_manager.detector.detect_provider", mock_detect), \
             patch("key_manager.providers.PROVIDERS", {"deepseek": mock_provider}), \
             patch("httpx.AsyncClient.post", return_value=mock_response):
            resp = client.post(
                "/api/check/single",
                json={"key": "sk-test-key-12345", "model": "deepseek-chat"}
            )
        
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert body["status"] == "valid"

    def test_check_single_without_model_auto_detected(self, client):
        """When provider is auto-detected and no model specified, should test all models."""
        from unittest.mock import AsyncMock, MagicMock, patch
        
        # Mock detect_provider to return a provider name
        mock_detect = AsyncMock(return_value="deepseek")
        
        # Mock the provider's check method
        mock_check_result = MagicMock()
        mock_check_result.valid = True
        mock_check_result.status_code = 200
        mock_check_result.latency_ms = 100.0
        mock_check_result.error = None
        
        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=mock_check_result)
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
        mock_provider.get_base_url.return_value = "https://api.deepseek.com/v1"
        mock_provider.check_endpoint = "/models"
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(supported=False))
        mock_provider.get_models = AsyncMock(return_value=["model-1", "model-2"])
        
        with patch("key_manager.detector.detect_provider", mock_detect), \
             patch("key_manager.providers.PROVIDERS", {"deepseek": mock_provider}):
            resp = client.post(
                "/api/check/single",
                json={"key": "sk-test-key-12345"}
            )
        
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert body["status"] == "valid"


# =============================================================================
# Test Token / Concurrency Endpoints
# =============================================================================


class TestTestTokenEndpoint:
    """Tests for /api/test/token endpoint."""

    def test_test_token_starts_async(self, client):
        """POST /api/test/token starts async token test."""
        resp = client.post("/api/test/token")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Token test started"
        assert body["status"] == "loading"

    def test_test_token_batch_starts_async(self, client):
        """POST /api/test/token/batch starts async token test (alias)."""
        resp = client.post("/api/test/token/batch")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Token test started"
        assert body["status"] == "loading"


class TestTestConcurrencyEndpoint:
    """Tests for /api/test/concurrency endpoint."""

    def test_test_concurrency_starts_async(self, client):
        """POST /api/test/concurrency starts async concurrency test."""
        resp = client.post("/api/test/concurrency")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Concurrency test started"
        assert body["status"] == "loading"

    def test_test_concurrency_batch_starts_async(self, client):
        """POST /api/test/concurrency/batch starts async concurrency test (alias)."""
        resp = client.post("/api/test/concurrency/batch")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Concurrency test started"
        assert body["status"] == "loading"


class TestModelsCapabilitiesEndpoint:
    """Tests for /api/models/capabilities endpoint."""

    def test_models_capabilities_empty(self, client):
        """GET /api/models/capabilities with empty models returns empty."""
        resp = client.get("/api/models/capabilities?models=")
        assert resp.status_code == 200
        body = resp.json()
        assert "capabilities" in body
        assert body["capabilities"] == {}

    def test_models_capabilities_with_models(self, client):
        """GET /api/models/capabilities with model IDs returns capabilities."""
        resp = client.get("/api/models/capabilities?models=gpt-4o,claude-3-opus")
        assert resp.status_code == 200
        body = resp.json()
        assert "capabilities" in body
        # Each model should have capability entries
        for model_id in ["gpt-4o", "claude-3-opus"]:
            assert model_id in body["capabilities"]


class TestModelsCheckEndpoint:
    """Tests for /api/models/check endpoint (SSE stream)."""

    def test_models_check_missing_provider(self, client):
        """POST /api/models/check without provider returns error."""
        resp = client.post("/api/models/check", json={})
        # Should return 400 for missing provider
        assert resp.status_code == 400

    def test_models_check_with_provider(self, client):
        """POST /api/models/check with provider starts SSE stream."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])
        mock_provider.check = AsyncMock(return_value=MagicMock(valid=True, status_code=200, latency_ms=50.0, error=None, error_type=None))
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test"}
        mock_provider.get_base_url.return_value = "https://api.openai.com/v1"
        mock_provider.check_endpoint = "/models"

        with patch("key_manager.providers.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test-12345"})
        # SSE endpoint returns 200 with text/event-stream
        assert resp.status_code == 200


class TestProgressStreamEndpoint:
    """Tests for /api/progress/stream endpoint (SSE stream)."""

    def test_progress_stream_returns_sse(self, client):
        """GET /api/progress/stream returns SSE stream."""
        resp = client.get("/api/progress/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
