"""Tests for all provider management endpoints in web/routes/providers.py.

Covers:
- GET /api/providers                  (list providers)
- GET /api/providers/detail           (detailed provider list)
- GET /api/providers/{name}           (get single provider)
- POST /api/providers                 (create custom provider)
- PUT /api/providers/{name}           (update custom provider)
- DELETE /api/providers/{name}        (delete custom provider)
- POST /api/providers/{name}/test     (test provider connectivity)
- _get_custom_provider_names() helper
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_provider(name="openai"):
    """Create a minimal mock provider with all required attributes."""
    p = MagicMock()
    p.name = name
    p.display_name = name.title()
    p.base_url = f"https://api.{name}.com"
    p.check_endpoint = "/v1/models"
    p.chat_endpoint = "/v1/chat/completions"
    p.key_prefixes = [f"{name[:3]}-"]
    p.error_signatures = [name]
    p.website_url = f"https://{name}.com"
    p.docs_url = f"https://docs.{name}.com"
    p.get_models = AsyncMock(return_value=["model-1", "model-2"])
    return p


def _provider_body(name="my-llm"):
    """Minimal valid body for creating a custom provider."""
    return {
        "name": name,
        "base_url": "https://api.my-llm.com/v1",
        "check_endpoint": "/models",
    }


# Patch paths for CRUD operations (lazy imports inside route functions)
REGISTRY_PATCH = "key_manager.providers._PROVIDER_REGISTRY"
SAVE_PATCH = "key_manager.providers.config_providers.save_custom_provider"
CREATE_PATCH = "key_manager.providers.config_providers._create_provider_from_config"
REMOVE_PATCH = "key_manager.providers.config_providers.remove_custom_provider"
CUSTOM_NAMES_PATCH = "key_manager.web.routes.providers._get_custom_provider_names"


# ── _get_custom_provider_names() ────────────────────────────────────────


class TestGetCustomProviderNames:
    """Tests for the _get_custom_provider_names helper."""

    def test_returns_set_on_valid_yaml(self, tmp_path, monkeypatch):
        """Reads custom provider names from config.yaml."""
        import key_manager.web.routes.providers as mod

        yaml_content = (
            "providers:\n"
            "  custom:\n"
            "    - name: my-llm\n"
            "    - name: another\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = mod._get_custom_provider_names()
        assert result == {"my-llm", "another"}

    def test_returns_empty_on_no_file(self, tmp_path, monkeypatch):
        """Returns empty set when config.yaml doesn't exist."""
        import key_manager.web.routes.providers as mod
        monkeypatch.chdir(tmp_path)

        result = mod._get_custom_provider_names()
        assert result == set()

    def test_returns_empty_when_no_custom_key(self, tmp_path, monkeypatch):
        """Returns empty set when providers.custom is missing."""
        import key_manager.web.routes.providers as mod

        config_file = tmp_path / "config.yaml"
        config_file.write_text("providers:\n  other: true\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = mod._get_custom_provider_names()
        assert result == set()


# ── GET /api/providers ──────────────────────────────────────────────────


class TestListProviders:
    """Tests for GET /api/providers."""

    def test_empty_providers(self, client):
        """Returns empty list when no providers registered."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.get("/api/providers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["providers"] == []
        assert body["total"] == 0

    def test_lists_single_provider(self, client):
        """Returns one provider with correct fields."""
        mock_p = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            resp = client.get("/api/providers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        p = body["providers"][0]
        assert p["name"] == "openai"
        assert "base_url" in p
        assert "display_name" in p
        assert "type" in p

    def test_lists_multiple_providers(self, client):
        """Returns multiple providers."""
        mock_openai = _mock_provider("openai")
        mock_deepseek = _mock_provider("deepseek")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_openai, "deepseek": mock_deepseek}):
            resp = client.get("/api/providers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        names = {p["name"] for p in body["providers"]}
        assert names == {"openai", "deepseek"}

    def test_prefix_is_dash_when_no_match(self, client):
        """Prefix defaults to '-' when provider not in KEY_PREFIX_MAP."""
        mock_p = _mock_provider("unknown-provider")
        with patch("key_manager.web._app.PROVIDERS", {"unknown-provider": mock_p}):
            resp = client.get("/api/providers")

        assert resp.status_code == 200
        body = resp.json()
        assert body["providers"][0]["prefix"] == "-"


# ── GET /api/providers/detail ───────────────────────────────────────────


class TestProvidersDetail:
    """Tests for GET /api/providers/detail."""

    def test_empty_detail_list(self, client):
        """Returns empty list when no providers."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.get("/api/providers/detail")

        assert resp.status_code == 200
        body = resp.json()
        assert body["providers"] == []
        assert body["total"] == 0

    def test_detail_includes_website_and_docs(self, client):
        """Detail response includes website_url and docs_url."""
        mock_p = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            resp = client.get("/api/providers/detail")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        p = body["providers"][0]
        assert p["name"] == "openai"
        assert "website_url" in p
        assert "docs_url" in p
        assert "website_name" in p


# ── GET /api/providers/{provider_name} ──────────────────────────────────


class TestGetProvider:
    """Tests for GET /api/providers/{provider_name}."""

    def test_get_existing_provider(self, client):
        """Returns full config for an existing provider."""
        mock_p = _mock_provider("openai")
        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            with patch(CUSTOM_NAMES_PATCH, return_value=set()):
                resp = client.get("/api/providers/openai")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "openai"
        assert body["base_url"] == "https://api.openai.com"
        assert body["check_endpoint"] == "/v1/models"
        assert body["source"] == "builtin"

    def test_get_custom_provider_source(self, client):
        """Custom provider shows source='custom'."""
        mock_p = _mock_provider("my-llm")
        with patch("key_manager.web._app.PROVIDERS", {"my-llm": mock_p}):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                resp = client.get("/api/providers/my-llm")

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "custom"

    def test_get_unknown_provider_returns_400(self, client):
        """Returns 400 for unknown provider."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.get("/api/providers/nonexistent")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"


# ── POST /api/providers ─────────────────────────────────────────────────


class TestCreateProvider:
    """Tests for POST /api/providers."""

    def test_create_success(self, client):
        """Successfully creates a new custom provider."""
        mock_registry = {}
        mock_created = MagicMock()
        mock_created.name = "my-llm"

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(SAVE_PATCH):
                with patch(CREATE_PATCH, return_value=mock_created):
                    resp = client.post("/api/providers", json=_provider_body())

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["provider"]["name"] == "my-llm"
        assert "my-llm" in mock_registry

    def test_create_missing_name(self, client):
        """Returns 400 when 'name' field is missing."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.post("/api/providers", json={"base_url": "https://x.com", "check_endpoint": "/models"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"
        assert "name" in body["error"]["message"]

    def test_create_missing_base_url(self, client):
        """Returns 400 when 'base_url' field is missing."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.post("/api/providers", json={"name": "test", "check_endpoint": "/models"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"
        assert "base_url" in body["error"]["message"]

    def test_create_missing_check_endpoint(self, client):
        """Returns 400 when 'check_endpoint' field is missing."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.post("/api/providers", json={"name": "test", "base_url": "https://x.com"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"
        assert "check_endpoint" in body["error"]["message"]

    def test_create_duplicate_name(self, client):
        """Returns 400 when provider already exists in registry."""
        existing = {"my-llm": MagicMock()}

        with patch(REGISTRY_PATCH, existing, create=True):
            resp = client.post("/api/providers", json=_provider_body())

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "already exists" in body["error"]["message"]

    def test_create_save_failure(self, client):
        """Returns 400 when save_custom_provider raises."""
        mock_registry = {}
        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(SAVE_PATCH, side_effect=IOError("disk full")):
                resp = client.post("/api/providers", json=_provider_body())

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "disk full" in body["error"]["message"]

    def test_create_invalid_json_body(self, client):
        """Returns 400 when request body is not valid JSON."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.post(
                "/api/providers",
                content=b"not json",
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "Invalid JSON" in body["error"]["message"]


# ── PUT /api/providers/{provider_name} ──────────────────────────────────


class TestUpdateProvider:
    """Tests for PUT /api/providers/{provider_name}."""

    def test_update_success(self, client):
        """Successfully updates a custom provider."""
        mock_registry = {"my-llm": MagicMock()}
        mock_updated = MagicMock()
        mock_updated.name = "my-llm"

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                with patch(SAVE_PATCH):
                    with patch(CREATE_PATCH, return_value=mock_updated):
                        resp = client.put("/api/providers/my-llm", json={"base_url": "https://updated.com"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_update_unknown_provider_returns_400(self, client):
        """Returns 400 when provider doesn't exist in registry."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.put("/api/providers/nonexistent", json={"base_url": "https://x.com"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_update_builtin_provider_returns_400(self, client):
        """Returns 400 when trying to update a builtin provider."""
        mock_registry = {"openai": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value=set()):
                resp = client.put("/api/providers/openai", json={"base_url": "https://x.com"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "builtin" in body["error"]["message"]

    def test_update_save_failure(self, client):
        """Returns 400 when save fails during update."""
        mock_registry = {"my-llm": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                with patch(SAVE_PATCH, side_effect=IOError("write error")):
                    resp = client.put("/api/providers/my-llm", json={"base_url": "https://x.com"})

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "write error" in body["error"]["message"]

    def test_update_invalid_json_body(self, client):
        """Returns 400 when request body is not valid JSON during update."""
        mock_registry = {"my-llm": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                resp = client.put(
                    "/api/providers/my-llm",
                    content=b"not json",
                    headers={"Content-Type": "application/json"},
                )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "Invalid JSON" in body["error"]["message"]


# ── DELETE /api/providers/{provider_name} ────────────────────────────────


class TestDeleteProvider:
    """Tests for DELETE /api/providers/{provider_name}."""

    def test_delete_success(self, client):
        """Successfully deletes a custom provider."""
        mock_registry = {"my-llm": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                with patch(REMOVE_PATCH):
                    resp = client.delete("/api/providers/my-llm")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "my-llm" not in mock_registry

    def test_delete_unknown_provider_returns_400(self, client):
        """Returns 400 when provider doesn't exist."""
        with patch(REGISTRY_PATCH, {}, create=True):
            resp = client.delete("/api/providers/nonexistent")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_delete_builtin_provider_returns_400(self, client):
        """Returns 400 when trying to delete a builtin provider."""
        mock_registry = {"openai": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value=set()):
                resp = client.delete("/api/providers/openai")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "builtin" in body["error"]["message"]

    def test_delete_failure_returns_400(self, client):
        """Returns 400 when remove_custom_provider raises."""
        mock_registry = {"my-llm": MagicMock()}

        with patch(REGISTRY_PATCH, mock_registry, create=True):
            with patch(CUSTOM_NAMES_PATCH, return_value={"my-llm"}):
                with patch(REMOVE_PATCH, side_effect=IOError("perm denied")):
                    resp = client.delete("/api/providers/my-llm")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_INVALID_FORMAT"
        assert "perm denied" in body["error"]["message"]


# ── POST /api/providers/{provider_name}/test ────────────────────────────


class TestProviderTest:
    """Tests for POST /api/providers/{provider_name}/test."""

    def test_test_success(self, client):
        """Returns success with model count when connectivity works."""
        mock_p = _mock_provider("openai")
        mock_p.get_models = AsyncMock(return_value=["gpt-4", "gpt-3.5-turbo"])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            resp = client.post("/api/providers/openai/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["provider"] == "openai"
        assert body["models_count"] == 2
        assert len(body["sample_models"]) == 2

    def test_test_unknown_provider_returns_400(self, client):
        """Returns 400 when provider not found."""
        with patch("key_manager.web._app.PROVIDERS", {}):
            resp = client.post("/api/providers/nonexistent/test")

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_test_failure_returns_success_false(self, client):
        """Returns success=False when get_models raises."""
        mock_p = _mock_provider("openai")
        mock_p.get_models = AsyncMock(side_effect=Exception("connection timeout"))

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            resp = client.post("/api/providers/openai/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["provider"] == "openai"
        assert "connection timeout" in body["error"]

    def test_test_empty_models(self, client):
        """Handles empty models list gracefully."""
        mock_p = _mock_provider("openai")
        mock_p.get_models = AsyncMock(return_value=[])

        with patch("key_manager.web._app.PROVIDERS", {"openai": mock_p}):
            resp = client.post("/api/providers/openai/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["models_count"] == 0
        assert body["sample_models"] == []
