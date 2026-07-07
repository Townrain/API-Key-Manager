"""Tests for misc routes: proxy, logs, progress, webhooks, signature report.

Covers key_manager/web/routes/misc.py — targeting ≥80% coverage.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch



# ── PROXY ────────────────────────────────────────────────────────────────────


class TestProxy:
    """GET /api/proxy — three source paths: config, auto, none."""

    def test_proxy_from_config(self, client):
        """When config has a non-empty proxy, source='config'."""
        with patch("key_manager.web._app.config", {"proxy": "http://my-proxy:8080"}):
            with patch("key_manager.web.routes.misc.get_proxy", return_value="http://my-proxy:8080"):
                resp = client.get("/api/proxy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proxy"] == "http://my-proxy:8080"
        assert body["source"] == "config"

    def test_proxy_auto_detected(self, client):
        """When config proxy is empty but auto-detect finds one, source='auto'."""
        with patch("key_manager.web._app.config", {"proxy": ""}):
            with patch("key_manager.web.routes.misc.get_proxy", return_value="http://127.0.0.1:7890"):
                resp = client.get("/api/proxy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proxy"] == "http://127.0.0.1:7890"
        assert body["source"] == "auto"

    def test_proxy_none(self, client):
        """When no proxy is available, source='none' and proxy=None."""
        with patch("key_manager.web._app.config", {"proxy": ""}):
            with patch("key_manager.web.routes.misc.get_proxy", return_value=""):
                resp = client.get("/api/proxy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["proxy"] is None
        assert body["source"] == "none"


# ── LOGS ─────────────────────────────────────────────────────────────────────


class TestLogs:
    """GET /api/logs, GET /api/logs/operations, DELETE /api/logs."""

    def test_get_logs(self, client):
        mock_logger = MagicMock()
        with patch("key_manager.web.routes.misc.get_project_logger") as mock_get:
            mock_get.return_value = mock_logger
            mock_logger.get_recent_logs.return_value = ["line1", "line2"]
            resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert resp.json()["logs"] == ["line1", "line2"]

    def test_get_operations(self, client):
        ops = [{"timestamp": "2024-01-01T00:00:00", "operation": "check", "status": "ok"}]
        mock_logger = MagicMock()
        with patch("key_manager.web.routes.misc.get_project_logger") as mock_get:
            mock_get.return_value = mock_logger
            mock_logger.get_operations_log.return_value = ops
            resp = client.get("/api/logs/operations")
        assert resp.status_code == 200
        assert len(resp.json()["operations"]) == 1

    def test_clear_logs(self, client):
        mock_logger = MagicMock()
        with patch("key_manager.web.routes.misc.get_project_logger") as mock_get:
            mock_get.return_value = mock_logger
            mock_logger.clear_main_log.return_value = {"success": True, "cleared": 1}
            resp = client.delete("/api/logs")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_logger.clear_main_log.assert_called_once_with(None)

    def test_clear_logs_with_date(self, client):
        mock_logger = MagicMock()
        with patch("key_manager.web.routes.misc.get_project_logger") as mock_get:
            mock_get.return_value = mock_logger
            mock_logger.clear_main_log.return_value = {"success": True, "cleared": 1}
            resp = client.delete("/api/logs?date=2024-01-01")
        assert resp.status_code == 200
        mock_logger.clear_main_log.assert_called_once_with("2024-01-01")


# ── PROGRESS ─────────────────────────────────────────────────────────────────


class TestProgress:
    """GET /api/progress, GET /api/progress/stream."""

    def test_progress_snapshot(self, client):
        snapshot = ProgressResponse(
            active=False, current=0, total=0, status="idle", results=None
        )
        with patch("key_manager.web.routes.misc._progress_tracker") as mock_tracker:
            mock_tracker.snapshot.return_value = snapshot
            resp = client.get("/api/progress")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active"] is False
        assert body["status"] == "idle"

    def test_progress_stream(self, client):
        """SSE stream returns event-stream content type."""
        resp = client.get("/api/progress/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]


# Need the model for snapshot return
from key_manager.api_models import ProgressResponse


# ── WEBHOOKS ─────────────────────────────────────────────────────────────────


class TestWebhooks:
    """CRUD for /api/webhooks + delivery log endpoints."""

    def test_list_webhooks(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            mock_wh.list_all.return_value = [
                {"id": "wh-1", "url": "https://example.com", "events": ["key.imported"]}
            ]
            resp = client.get("/api/webhooks")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_webhook(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            mock_wh.register.return_value = "wh-new-123"
            resp = client.post("/api/webhooks", json={
                "url": "https://example.com/hook",
                "events": ["key.imported"],
                "secret": "s3cret",
                "active": True,
                "max_retries": 3,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["webhook_id"] == "wh-new-123"
        mock_wh.register.assert_called_once()

    def test_create_webhook_invalid_json(self, client):
        """Invalid JSON body raises 400."""
        resp = client.post(
            "/api/webhooks",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_get_webhook_found(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            mock_wh.get.return_value = {"id": "wh-1", "url": "https://example.com"}
            resp = client.get("/api/webhooks/wh-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "wh-1"

    def test_get_webhook_not_found(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            mock_wh.get.return_value = None
            resp = client.get("/api/webhooks/wh-nonexistent")
        assert resp.status_code == 404

    def test_update_webhook(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            resp = client.put("/api/webhooks/wh-1", json={"url": "https://new-url.com"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_wh.update.assert_called_once_with("wh-1", url="https://new-url.com")

    def test_update_webhook_invalid_json(self, client):
        """Invalid JSON body raises 400."""
        resp = client.put(
            "/api/webhooks/wh-1",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_delete_webhook(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            resp = client.delete("/api/webhooks/wh-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_wh.unregister.assert_called_once_with("wh-1")

    def test_list_delivery_logs(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            mock_wh.get_delivery_log.return_value = [
                {"webhook_url": "https://example.com", "event": "key.imported", "success": True}
            ]
            resp = client.get("/api/webhooks/log/deliveries")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_clear_delivery_logs(self, client):
        with patch("key_manager.web.routes.misc.webhook_manager") as mock_wh:
            resp = client.delete("/api/webhooks/log/deliveries")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_wh.clear_delivery_log.assert_called_once()


# ── SIGNATURE REPORT ─────────────────────────────────────────────────────────


class TestSignatureReport:
    """GET /api/signature-report — async probe with timeout/exception/conflict paths."""

    @staticmethod
    def _make_provider(name, response_body="platform.openai.com error", status_code=401, error=None, valid=False):
        """Create a mock provider with a probe method."""
        provider = MagicMock()
        provider.name = name
        provider.probe = AsyncMock(return_value=SimpleNamespace(
            status_code=status_code,
            response_body=response_body,
            error=error,
            valid=valid,
        ))
        return provider

    def test_signature_report_success(self, client):
        """Normal path: one provider with full signature match."""
        mock_provider = self._make_provider("openai", response_body="platform.openai.com error")

        mock_sigs = {"openai": ["platform.openai.com"]}
        mock_providers = {"openai": mock_provider}

        with (
            patch("key_manager.web.routes.misc.PROVIDERS", mock_providers, create=True),
            patch("key_manager.web.routes.misc.PROVIDER_ERROR_SIGNATURES", mock_sigs, create=True),
        ):
            # The function does a local import — we need to patch inside the function.
            # Use a context manager that patches the module-level names the function imports.
            import key_manager.web.routes.misc as misc_mod

            # The function imports from key_manager.providers inside, so patch those
            with patch.dict("sys.modules", {}):
                pass  # not needed — just patch the globals used in the function

            # Actually, the function uses `from key_manager.providers import ...` locally.
            # We need to patch `key_manager.providers.PROVIDERS` and `key_manager.providers.PROVIDER_ERROR_SIGNATURES`.
            with (
                patch("key_manager.providers.PROVIDERS", mock_providers),
                patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
            ):
                resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_providers"] == 1
        assert body["summary"]["successful_tests"] == 1
        assert body["summary"]["full_match"] == 1
        assert body["results"][0]["provider"] == "openai"
        assert body["results"][0]["conflicts"] == []

    def test_signature_report_partial_match(self, client):
        """Provider returns body matching only some signatures."""
        mock_provider = self._make_provider("openai", response_body="some openai platform.openai.com text")

        mock_sigs = {"openai": ["platform.openai.com", "missing-signature"]}
        mock_providers = {"openai": mock_provider}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["partial_match"] == 1
        result = body["results"][0]
        assert "platform.openai.com" in result["unique_signatures"]["matched"]
        assert "missing-signature" in result["unique_signatures"]["missing"]

    def test_signature_report_timeout(self, client):
        """Provider probe times out."""
        mock_provider = MagicMock()
        mock_provider.name = "openai"
        mock_provider.probe = AsyncMock(side_effect=asyncio.TimeoutError)

        mock_sigs = {"openai": ["platform.openai.com"]}
        mock_providers = {"openai": mock_provider}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        result = body["results"][0]
        assert result["status_code"] is None
        assert result["error"] == "timeout"
        assert result["valid"] is False
        assert body["summary"]["successful_tests"] == 0

    def test_signature_report_exception(self, client):
        """Provider probe raises a generic exception."""
        mock_provider = MagicMock()
        mock_provider.name = "openai"
        mock_provider.probe = AsyncMock(side_effect=ConnectionError("connection refused"))

        mock_sigs = {"openai": ["platform.openai.com"]}
        mock_providers = {"openai": mock_provider}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        result = body["results"][0]
        assert result["status_code"] is None
        assert result["error"] == "connection refused"
        assert result["valid"] is False

    def test_signature_report_conflicts(self, client):
        """Two providers share a signature → conflict detected."""
        mock_openai = self._make_provider("openai", response_body="anthropic x-api-key error")
        mock_anthropic = self._make_provider("anthropic", response_body="anthropic x-api-key error")

        mock_sigs = {
            "openai": ["platform.openai.com"],
            "anthropic": ["anthropic", "x-api-key"],
        }
        mock_providers = {"openai": mock_openai, "anthropic": mock_anthropic}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        # openai provider's response contains "anthropic" and "x-api-key" → conflicts
        openai_result = next(r for r in body["results"] if r["provider"] == "openai")
        assert len(openai_result["conflicts"]) >= 1
        assert any(c["other_provider"] == "anthropic" for c in openai_result["conflicts"])

    def test_signature_report_no_signatures(self, client):
        """Provider with empty signature list — match_rate should be 0."""
        mock_provider = self._make_provider("together", response_body="some error body")

        mock_sigs = {"together": []}
        mock_providers = {"together": mock_provider}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        result = body["results"][0]
        assert result["unique_signatures"]["total"] == 0
        assert result["unique_signatures"]["match_rate"] == 0

    def test_signature_report_new_signatures(self, client):
        """Extracted words not in known signatures appear as new_signatures."""
        mock_provider = self._make_provider("openai", response_body="platform.openai.com some-new-keyword-xyz error")

        mock_sigs = {"openai": ["platform.openai.com"]}
        mock_providers = {"openai": mock_provider}

        with (
            patch("key_manager.providers.PROVIDERS", mock_providers),
            patch("key_manager.providers.PROVIDER_ERROR_SIGNATURES", mock_sigs),
        ):
            resp = client.get("/api/signature-report")

        assert resp.status_code == 200
        body = resp.json()
        result = body["results"][0]
        # "some-new-keyword-xyz" should be extracted as a new signature
        assert any("some-new-keyword" in s for s in result["new_signatures"])
