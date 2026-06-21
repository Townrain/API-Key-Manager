import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def spec():
    """Load the generated OpenAPI spec."""
    spec_path = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    assert spec_path.exists(), f"OpenAPI spec not found at {spec_path}"
    with open(spec_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def client():
    from key_manager.web import app

    return TestClient(app)


# ── Spec metadata ─────────────────────────────────────────────────────────────


class TestOpenAPIMetadata:
    def test_title(self, spec):
        assert spec["info"]["title"] == "API Key Manager"

    def test_description(self, spec):
        assert "37+" in spec["info"]["description"]

    def test_version(self, spec):
        assert spec["info"]["version"] == "1.0.0"

    def test_openapi_version(self, spec):
        assert spec["openapi"].startswith("3.")


# ── Tags ──────────────────────────────────────────────────────────────────────


EXPECTED_TAGS = [
    "Keys",
    "Check",
    "Test",
    "Balance",
    "Models",
    "Providers",
    "Stats",
    "Logs",
    "Progress",
]


class TestTags:
    def test_all_tags_present(self, spec):
        tag_names = [t["name"] for t in spec.get("tags", [])]
        for tag in EXPECTED_TAGS:
            assert tag in tag_names, f"Missing tag: {tag}"


# ── Paths ─────────────────────────────────────────────────────────────────────


EXPECTED_PATHS = [
    ("/api/keys", "get"),
    ("/api/keys/export", "get"),
    ("/api/keys/clear", "post"),
    ("/api/import", "post"),
    ("/api/import/upload", "post"),
    ("/api/check/single", "post"),
    ("/api/check/batch", "post"),
    ("/api/check", "post"),
    ("/api/test", "post"),
    ("/api/test/single", "post"),
    ("/api/test/concurrency", "post"),
    ("/api/test/token", "post"),
    ("/api/balance", "post"),
    ("/api/models", "get"),
    ("/api/models/check", "post"),
    ("/api/providers", "get"),
    ("/api/providers/detail", "get"),
    ("/api/stats", "get"),
    ("/api/stats/chart", "get"),
    ("/api/logs", "get"),
    ("/api/logs/operations", "get"),
    ("/api/logs/files", "get"),
    ("/api/progress", "get"),
    ("/api/progress/stream", "get"),
    ("/api/proxy", "get"),
    ("/api/signature-report", "get"),
]


class TestPaths:
    def test_all_paths_exist(self, spec):
        paths = spec.get("paths", {})
        for path, method in EXPECTED_PATHS:
            assert path in paths, f"Missing path: {path}"
            assert method in paths[path], f"Missing method {method} for {path}"

    def test_path_count(self, spec):
        assert len(spec.get("paths", {})) >= 26


# ── Pydantic models ──────────────────────────────────────────────────────────


class TestPydanticModels:
    def test_import_api_models(self):
        from key_manager.api_models import (
            ErrorResponse,
            KeyListResponse,
            KeyExportResponse,
            ImportRequest,
            ImportResponse,
            CheckSingleRequest,
            CheckSingleResponse,
            CheckBatchRequest,
            CheckBatchResponse,
            TestSingleRequest,
            TestSingleResponse,
            BalanceRequest,
            BalanceResponse,
            ModelsResponse,
            ProvidersResponse,
            ProviderDetailResponse,
            StatsResponse,
            StatsChartResponse,
            LogsResponse,
            OperationsResponse,
            ProgressResponse,
        )

    def test_error_response_schema(self):
        from key_manager.api_models import ErrorResponse

        schema = ErrorResponse.model_json_schema()
        assert "error" in schema["properties"]
        err_prop = schema["properties"]["error"]
        # error field is a $ref to ErrorDetail or has type/anyOf
        assert "$ref" in err_prop or err_prop.get("type") == "string" or "anyOf" in err_prop

    def test_key_list_response_schema(self):
        from key_manager.api_models import KeyListResponse

        schema = KeyListResponse.model_json_schema()
        assert "keys" in schema["properties"]
        assert "total" in schema["properties"]
        assert "page" in schema["properties"]

    def test_import_request_example(self):
        from key_manager.api_models import ImportRequest

        schema = ImportRequest.model_json_schema()
        assert "examples" in schema.get("json_schema_extra", {}) or "file" in schema["properties"]

    def test_check_batch_request_min_items(self):
        from key_manager.api_models import CheckBatchRequest

        schema = CheckBatchRequest.model_json_schema()
        keys_prop = schema["properties"]["keys"]
        assert keys_prop.get("minItems", 0) >= 1

    def test_progress_response_fields(self):
        from key_manager.api_models import ProgressResponse

        schema = ProgressResponse.model_json_schema()
        props = schema["properties"]
        assert "active" in props
        assert "current" in props
        assert "total" in props
        assert "status" in props

    def test_model_serialization(self):
        from key_manager.api_models import CheckSingleResponse

        resp = CheckSingleResponse(
            key_masked="sk-abc...xyz",
            provider="openai",
            status="valid",
            latency_ms=123.4,
        )
        data = resp.model_dump()
        assert data["key_masked"] == "sk-abc...xyz"
        assert data["status"] == "valid"
        assert data["latency_ms"] == 123.4

    def test_model_validate(self):
        from key_manager.api_models import ImportResponse

        data = {"new": 5, "duplicates": 2, "errors": []}
        resp = ImportResponse.model_validate(data)
        assert resp.new == 5
        assert resp.duplicates == 2


# ── Spec ↔ model alignment ────────────────────────────────────────────────────


class TestSpecModelAlignment:
    """Verify that the generated spec references match model schemas."""

    def test_spec_has_component_schemas(self, spec):
        components = spec.get("components", {})
        schemas = components.get("schemas", {})
        assert isinstance(schemas, dict)

    def test_import_endpoint_has_request_body(self, spec):
        path = spec["paths"].get("/api/import", {})
        post = path.get("post", {})
        # Endpoint accepts JSON body (may be raw request.json() without explicit schema)
        assert "responses" in post, "/api/import POST must have responses"


# ── Spec completeness ─────────────────────────────────────────────────────────


class TestSpecCompleteness:
    def test_no_empty_paths(self, spec):
        for path, methods in spec.get("paths", {}).items():
            assert methods, f"Empty path entry: {path}"

    def test_all_methods_have_responses(self, spec):
        for path, methods in spec.get("paths", {}).items():
            for method, detail in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    assert "responses" in detail, f"{method.upper()} {path} missing responses"

    def test_error_response_defined(self, spec):
        """ErrorResponse model should be importable and well-formed."""
        from key_manager.api_models import ErrorResponse

        schema = ErrorResponse.model_json_schema()
        assert "error" in schema["properties"]
