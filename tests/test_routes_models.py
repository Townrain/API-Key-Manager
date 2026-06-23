"""Tests for endpoints in key_manager/web/routes/models.py.

Covers:
- GET /api/models  (auto-detect, live fetch, static fallback, type filters)
- GET /api/models/capabilities  (normal, empty, exception)
- POST /api/models/check  (SSE stream: with/without provider, empty, retry)
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_config, write_keys_file, make_keys_data


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_provider(name="openai", models=None, include_probe=False):
    """Create a mock provider with configurable behavior for models tests."""
    provider = MagicMock()
    provider.name = name
    provider.base_url = f"https://api.{name}.com/v1"
    provider.check_endpoint = "/models"
    provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
    provider.get_base_url.return_value = provider.base_url
    provider.get_models = AsyncMock(return_value=models or ["gpt-4", "gpt-3.5-turbo"])
    if include_probe:
        provider._probe_model = AsyncMock(return_value=True)
    return provider


# ── GET /api/models ─────────────────────────────────────────────────────────


class TestModelsList:
    """Tests for GET /api/models endpoint."""

    def test_no_provider_no_key_returns_all_static(self, client):
        """No provider, no key → all static models from PROVIDER_MODELS."""
        resp = client.get("/api/models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "all"
        assert body["source"] == "static"
        assert body["total"] > 0
        assert len(body["models"]) > 0

    def test_no_provider_with_key_auto_detects(self, client):
        """No provider but key given → auto-detect from key."""
        mock_provider = _mock_provider("deepseek", models=["deepseek-chat"])

        with patch("key_manager.web._app.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.get("/api/models?key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "deepseek"
        assert "deepseek-chat" in body["models"]

    def test_no_provider_auto_detect_unknown_returns_empty(self, client):
        """Auto-detect returns 'unknown' → empty response with hint (line 44)."""
        with patch("key_manager.web._app.PROVIDERS", {"openai": _mock_provider("openai")}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="unknown")):
                resp = client.get("/api/models?key=bad-key-123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "unknown"
        assert body["models"] == []
        assert body["total"] == 0
        assert body.get("hint") is not None

    def test_no_provider_auto_detect_not_in_providers(self, client):
        """Auto-detect returns a provider not in PROVIDERS → empty with hint."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="someprovider")):
                resp = client.get("/api/models?key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "unknown"
        assert body["models"] == []

    def test_provider_not_found(self, client):
        """Known provider name but not in PROVIDERS → empty with hint."""
        resp = client.get("/api/models?provider=nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "nonexistent"
        assert body["models"] == []
        assert body["total"] == 0
        assert body.get("hint") == "Provider not found"

    def test_provider_with_key_live_fetch(self, client):
        """Provider + key → live fetch via get_models (source=api)."""
        mock_provider = _mock_provider("openai", models=["gpt-4o", "gpt-4"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.get("/api/models?provider=openai&key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["source"] == "api"
        assert "gpt-4o" in body["models"]
        mock_provider.get_models.assert_called_once()

    def test_provider_with_key_get_models_exception_fallback(self, client):
        """get_models raises → falls back to static (lines 88-89)."""
        mock_provider = _mock_provider("openai", models=[])
        mock_provider.get_models = AsyncMock(side_effect=Exception("network error"))
        # No 'models' attr → fallback to PROVIDER_MODELS
        if hasattr(mock_provider, "models"):
            delattr(mock_provider, "models")

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.get("/api/models?provider=openai&key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        # Falls back to static
        assert body["source"] == "static"

    def test_provider_no_key_uses_static(self, client):
        """Provider specified but no key → static models from PROVIDER_MODELS."""
        resp = client.get("/api/models?provider=openai")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai"
        assert body["source"] == "static"
        assert body["total"] > 0

    def test_provider_fallback_to_models_attr(self, client):
        """get_models returns empty → falls back to provider.models attr."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=[])
        mock_provider.models = ["custom-model-a", "custom-model-b"]

        with patch("key_manager.web._app.PROVIDERS", {"testprov": mock_provider}):
            resp = client.get("/api/models?provider=testprov&key=sk-test123")

        assert resp.status_code == 200
        body = resp.json()
        assert "custom-model-a" in body["models"]
        assert "custom-model-b" in body["models"]


# ── Type Filter Tests ───────────────────────────────────────────────────────


class TestModelsTypeFilters:
    """Tests for type filter parameter (lines 102-117)."""

    def _run_with_filter(self, client, type_filter, mock_detector):
        """Helper to run models request with a type filter and mocked detector."""
        mock_provider = _mock_provider("openai", models=["gpt-4o", "gpt-3.5-turbo", "text-embedding-3-small"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.model_capabilities.detector", mock_detector):
                resp = client.get(f"/api/models?provider=openai&key=sk-test123&type_filter={type_filter}")

        assert resp.status_code == 200
        return resp.json()

    def test_filter_vision(self, client):
        """Type filter 'vision' returns only vision models (line 103)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_vision_model = lambda m: m == "gpt-4o"

        body = self._run_with_filter(client, "vision", mock_detector)
        assert body["type_filter"] == "vision"
        assert "gpt-4o" in body["models"]
        assert "gpt-3.5-turbo" not in body["models"]

    def test_filter_tool(self, client):
        """Type filter 'tool' returns only tool models (line 105)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_tool_model = lambda m: m == "gpt-4o"

        body = self._run_with_filter(client, "tool", mock_detector)
        assert "gpt-4o" in body["models"]
        assert "gpt-3.5-turbo" not in body["models"]

    def test_filter_tooluse(self, client):
        """Type filter 'tooluse' also filters by is_tool_model (line 104)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_tool_model = lambda m: m == "gpt-4o"

        body = self._run_with_filter(client, "tooluse", mock_detector)
        assert "gpt-4o" in body["models"]
        assert "gpt-3.5-turbo" not in body["models"]

    def test_filter_websearch(self, client):
        """Type filter 'websearch' (line 107)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_websearch_model = lambda m: m == "gpt-4o"

        body = self._run_with_filter(client, "websearch", mock_detector)
        assert "gpt-4o" in body["models"]

    def test_filter_reasoning(self, client):
        """Type filter 'reasoning' (line 109)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_reasoning_model = lambda m: m == "gpt-4o"

        body = self._run_with_filter(client, "reasoning", mock_detector)
        assert "gpt-4o" in body["models"]

    def test_filter_embedding(self, client):
        """Type filter 'embedding' (line 111)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_embedding_model = lambda m: m == "text-embedding-3-small"

        body = self._run_with_filter(client, "embedding", mock_detector)
        assert "text-embedding-3-small" in body["models"]
        assert "gpt-4o" not in body["models"]

    def test_filter_rerank(self, client):
        """Type filter 'rerank' (line 113)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_rerank_model = lambda m: m == "rerank-v1"

        mock_provider = _mock_provider("openai", models=["rerank-v1", "gpt-4o"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.model_capabilities.detector", mock_detector):
                resp = client.get("/api/models?provider=openai&key=sk-test123&type_filter=rerank")

        body = resp.json()
        assert "rerank-v1" in body["models"]
        assert "gpt-4o" not in body["models"]

    def test_filter_free(self, client):
        """Type filter 'free' (line 115)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock()
        mock_detector.is_free_model = lambda m: "free" in m

        mock_provider = _mock_provider("openai", models=["gpt-4-free", "gpt-4o"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.model_capabilities.detector", mock_detector):
                resp = client.get("/api/models?provider=openai&key=sk-test123&type_filter=free")

        body = resp.json()
        assert "gpt-4-free" in body["models"]
        assert "gpt-4o" not in body["models"]

    def test_filter_exception_falls_through(self, client):
        """Exception in detector.load() → no filtering, return all models (line 116-117)."""
        mock_detector = MagicMock()
        mock_detector.load = AsyncMock(side_effect=Exception("load failed"))

        mock_provider = _mock_provider("openai", models=["gpt-4o", "gpt-3.5-turbo"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.model_capabilities.detector", mock_detector):
                resp = client.get("/api/models?provider=openai&key=sk-test123&type_filter=vision")

        body = resp.json()
        # Filter exception → all models returned unfiltered
        assert len(body["models"]) == 2


# ── GET /api/models/capabilities ────────────────────────────────────────────


class TestModelsCapabilities:
    """Tests for GET /api/models/capabilities endpoint."""

    def test_empty_models_returns_empty(self, client):
        """Empty models query → empty capabilities."""
        resp = client.get("/api/models/capabilities?models=")
        assert resp.status_code == 200
        body = resp.json()
        assert body["capabilities"] == {}

    def test_with_model_ids(self, client):
        """Valid model IDs → capabilities dict for each model."""
        resp = client.get("/api/models/capabilities?models=gpt-4o,text-embedding-3-small")
        assert resp.status_code == 200
        body = resp.json()
        assert "gpt-4o" in body["capabilities"]
        assert "text-embedding-3-small" in body["capabilities"]
        # Each entry should have capability keys
        caps = body["capabilities"]["gpt-4o"]
        assert "vision" in caps
        assert "tooluse" in caps

    def test_exception_returns_error(self, client):
        """Exception in detector → returns empty capabilities with error (lines 146-147)."""
        with patch("key_manager.model_capabilities.detector") as mock_det:
            mock_det.load = AsyncMock(side_effect=Exception("load failed"))
            resp = client.get("/api/models/capabilities?models=gpt-4o")

        assert resp.status_code == 200
        body = resp.json()
        assert body["capabilities"] == {}
        assert "error" in body


# ── POST /api/models/check (SSE) ───────────────────────────────────────────


class TestModelsCheckSSE:
    """Tests for POST /api/models/check SSE endpoint."""

    def test_invalid_json_body(self, client):
        """Invalid JSON body → 400 VALIDATION_INVALID_FORMAT (lines 155-156)."""
        resp = client.post(
            "/api/models/check",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"

    def test_missing_key(self, client):
        """Empty key → 400 VALIDATION_MISSING_KEY."""
        resp = client.post("/api/models/check", json={"provider": "openai", "key": ""})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_with_provider_returns_sse(self, client):
        """With provider + key → SSE stream with models (lines 169-176)."""
        mock_provider = _mock_provider("openai", models=["gpt-4", "gpt-3.5-turbo"], include_probe=True)
        mock_provider._probe_model = AsyncMock(return_value=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # Parse SSE events from response text
        events = _parse_sse(resp.text)
        # Should have at least progress and complete events
        types = [e.get("type") for e in events]
        assert "progress" in types
        assert "complete" in types

    def test_with_provider_no_models_fallback_static(self, client):
        """Provider found but get_models returns empty → fallback to static (lines 190-193)."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=[])
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test"}
        mock_provider._probe_model = AsyncMock(return_value=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.web.routes.models.PROVIDER_MODELS", {"openai": ["gpt-4o-static"]}):
                resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        events = _parse_sse(resp.text)
        # Should have results for static models
        result_models = [e["model"] for e in events if e.get("type") == "result"]
        assert "gpt-4o-static" in result_models

    def test_without_provider_auto_detect(self, client):
        """No provider → auto-detect via detect_provider (lines 177-188)."""
        mock_provider = _mock_provider("deepseek", models=["deepseek-chat"], include_probe=True)

        with patch("key_manager.web._app.PROVIDERS", {"deepseek": mock_provider}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="deepseek")):
                resp = client.post("/api/models/check", json={"key": "sk-test123"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_empty_models_sse(self, client):
        """No models found at all → SSE complete event with 0 (lines 200-203)."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=[])
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test"}

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.web.routes.models.PROVIDER_MODELS", {}):
                resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        events = _parse_sse(resp.text)
        complete_events = [e for e in events if e.get("type") == "complete"]
        assert len(complete_events) >= 1
        assert complete_events[0]["available"] == 0
        assert complete_events[0]["total"] == 0

    def test_probe_success_returns_available(self, client):
        """All models probe successfully → available result events (lines 222, 244-246)."""
        mock_provider = _mock_provider("openai", models=["gpt-4"], include_probe=True)
        mock_provider._probe_model = AsyncMock(return_value=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        result_events = [e for e in events if e.get("type") == "result"]
        assert len(result_events) >= 1
        assert result_events[0]["available"] is True
        assert result_events[0]["model"] == "gpt-4"

    def test_probe_timeout_triggers_retry(self, client):
        """Probe times out → model_timeout event, then serial retry (lines 223-226, 257-274)."""
        call_count = {"n": 0}

        async def probe_timeout_then_ok(http, headers, model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise asyncio.TimeoutError("probe timeout")
            return True

        mock_provider = _mock_provider("openai", models=["gpt-4"], include_probe=True)
        mock_provider._probe_model = AsyncMock(side_effect=probe_timeout_then_ok)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        types = [e.get("type") for e in events]
        # Should have timeout, serial_mode, and retry result
        assert "model_timeout" in types
        assert "serial_mode" in types

    def test_probe_exception_returns_timeout(self, client):
        """Probe raises generic exception → model_timeout (line 228)."""
        mock_provider = _mock_provider("openai", models=["gpt-4"], include_probe=True)
        mock_provider._probe_model = AsyncMock(side_effect=RuntimeError("some error"))

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        timeout_events = [e for e in events if e.get("type") == "model_timeout"]
        assert len(timeout_events) >= 1

    def test_batch_success_increments_batch_size(self, client):
        """All models in batch succeed → batch_size increments (line 254)."""
        models = [f"model-{i}" for i in range(7)]
        mock_provider = _mock_provider("openai", models=models, include_probe=True)
        mock_provider._probe_model = AsyncMock(return_value=True)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        complete = [e for e in events if e.get("type") == "complete"][0]
        assert complete["available"] == 7
        assert complete["total"] == 7

    def test_serial_retry_skips_already_available(self, client):
        """In serial retry, skip models already available (line 263)."""
        call_log = []

        async def probe_fn(http, headers, model):
            call_log.append(model)
            # First call fails, but gpt-4 already marked available from batch
            if model == "gpt-4":
                return True
            return False

        mock_provider = _mock_provider("openai", models=["gpt-4", "gpt-3.5-turbo"], include_probe=True)
        mock_provider._probe_model = AsyncMock(side_effect=probe_fn)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        # Both should have result events
        result_events = [e for e in events if e.get("type") == "result"]
        assert len(result_events) >= 1

    def test_serial_retry_success(self, client):
        """Model fails in batch, succeeds in serial retry (lines 268-271)."""
        call_count = {"gpt-4": 0}

        async def probe_fn(http, headers, model):
            call_count.setdefault(model, 0)
            call_count[model] += 1
            # Fail first time, succeed on retry
            if model == "gpt-4" and call_count[model] == 1:
                raise asyncio.TimeoutError("timeout")
            return True

        mock_provider = _mock_provider("openai", models=["gpt-4"], include_probe=True)
        mock_provider._probe_model = AsyncMock(side_effect=probe_fn)

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            resp = client.post("/api/models/check", json={"provider": "openai", "key": "sk-test123"})

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        # Should have retry result
        retry_results = [e for e in events if e.get("type") == "result" and e.get("retry")]
        assert len(retry_results) >= 1
        assert retry_results[0]["available"] is True

    def test_detect_by_prefix_fallback(self, client):
        """No provider, detect fails → uses detect_by_prefix (lines 194-197)."""
        mock_provider = MagicMock()
        mock_provider.get_models = AsyncMock(return_value=[])
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test"}
        mock_provider._probe_model = AsyncMock(return_value=True)

        # detect_provider returns empty string → provider_name stays ""
        # This triggers detect_by_prefix fallback at lines 194-197
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_provider}):
            with patch("key_manager.web._app.detect_provider", new=AsyncMock(return_value="")):
                with patch("key_manager.web.routes.models.detect_by_prefix", return_value=["openai"]):
                    with patch("key_manager.web.routes.models.PROVIDER_MODELS", {"openai": ["gpt-4o"]}):
                        resp = client.post("/api/models/check", json={"key": "sk-test123"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


# ── SSE Parsing Helper ──────────────────────────────────────────────────────


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE data events from response text into a list of dicts."""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            payload = line[6:]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events
