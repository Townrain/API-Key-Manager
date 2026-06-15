import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("KEY_MANAGER_SECRET", "test-secret-for-e2e")
os.environ.setdefault("KEY_MANAGER_API_KEY", "test-api-key-12345")


def _write_keys(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _mock_check(*args, **kwargs):
    return SimpleNamespace(valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None)


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


def _make_keys_data():
    return {
        "keys": {
            "sk-test123456789": {
                "key": "sk-test123456789",
                "key_masked": "sk-tes...6789",
                "provider": "openai",
                "status": "unknown",
                "last_checked": None,
                "checks": [],
                "tests": {},
                "sources": [{"file": "test.json", "batch": "test"}],
            }
        },
        "metadata": {"created_at": "2024-01-01T00:00:00Z", "last_updated": "2024-01-01T00:00:00Z"},
    }


@pytest.fixture
def client(tmp_path):
    cfg = _make_config(tmp_path)
    with patch("key_manager.web.config", cfg):
        from key_manager.web import app
        yield TestClient(app, headers={"Authorization": "Bearer test-api-key-12345"})


class TestE2EWorkflow:
    """Import -> Check -> List -> Export full workflow tests."""

    def test_import_keys(self, client, tmp_path):
        cfg = _make_config(tmp_path)
        keys_data = _make_keys_data()

        def do_import(**kwargs):
            _write_keys(Path(cfg["storage"]["keys_file"]), keys_data)
            return (1, 0, [])

        with patch("key_manager.web.import_keys", side_effect=do_import), \
             patch("key_manager.web.validate_import_path", side_effect=lambda p, d: Path(p)):
            resp = client.post("/api/import", json={"file": "test.json"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["new"] == 1
            assert body["duplicates"] == 0
            assert body["errors"] == []

    def test_list_after_import(self, client, tmp_path):
        cfg = _make_config(tmp_path)
        keys_data = _make_keys_data()
        _write_keys(Path(cfg["storage"]["keys_file"]), keys_data)

        resp = client.get("/api/keys")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["keys"][0]["key_masked"] == "sk-tes...6789"

    def test_export_valid_keys(self, client, tmp_path):
        cfg = _make_config(tmp_path)
        keys_data = _make_keys_data()
        keys_data["keys"]["sk-test123456789"]["status"] = "valid"
        _write_keys(Path(cfg["storage"]["keys_file"]), keys_data)

        resp = client.get("/api/keys/export")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["keys"][0]["provider"] == "openai"

    def test_full_workflow(self, client, tmp_path):
        cfg = _make_config(tmp_path)
        keys_data = _make_keys_data()

        # Step 1: Import
        def do_import(**kwargs):
            _write_keys(Path(cfg["storage"]["keys_file"]), keys_data)
            return (1, 0, [])

        with patch("key_manager.web.import_keys", side_effect=do_import), \
             patch("key_manager.web.validate_import_path", side_effect=lambda p, d: Path(p)):
            resp = client.post("/api/import", json={"file": "test.json"})
            assert resp.status_code == 200
            assert resp.json()["new"] == 1

        # Step 2: Check
        check_result = {
            "total": 1,
            "summary": {"valid": {"count": 1}, "invalid": {"count": 0}, "error": {"count": 0}},
            "results": [],
        }
        with patch("key_manager.web.validate_keys", new=AsyncMock(return_value=check_result)):
            resp = client.post("/api/check", json={})
            assert resp.status_code == 200
            assert resp.json()["total"] == 1

        # Step 3: List
        keys_data["keys"]["sk-test123456789"]["status"] = "valid"
        keys_data["keys"]["sk-test123456789"]["checks"] = [{"status": "valid", "balance": None}]
        _write_keys(Path(cfg["storage"]["keys_file"]), keys_data)

        resp = client.get("/api/keys")
        assert resp.status_code == 200
        assert resp.json()["keys"][0]["status"] == "valid"

        # Step 4: Export
        resp = client.get("/api/keys/export")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestE2EErrorHandling:
    """Structured error response tests using ErrorResponse and t()."""

    def test_missing_key_returns_structured_error(self, client):
        resp = client.post("/api/check/single", json={"key": "", "provider": "openai"})
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"
        assert isinstance(body["error"]["message"], str)
        assert len(body["error"]["message"]) > 0

    def test_unsupported_provider_returns_structured_error(self, client):
        resp = client.post("/api/check/single", json={"key": "sk-test", "provider": "nonexistent"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"

    def test_batch_no_keys_returns_error(self, client):
        resp = client.post("/api/check/batch", json={"keys": []})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_balance_missing_key_returns_error(self, client):
        resp = client.post("/api/balance", json={"key": "", "provider": "openai"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"

    def test_upload_no_file_returns_error(self, client):
        resp = client.post("/api/import/upload")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_FILE_NOT_FOUND"

    def test_clear_empty_returns_zero(self, client, tmp_path):
        resp = client.post("/api/keys/clear")
        assert resp.status_code == 200
        assert resp.json()["cleared"] == 0

    def test_keys_empty_when_no_file(self, client):
        resp = client.get("/api/keys")
        assert resp.status_code == 200
        body = resp.json()
        assert body["keys"] == []
        assert body["total"] == 0


class TestE2EI18N:
    """Internationalization tests for language switching."""

    def test_error_message_in_chinese(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "zh-CN"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_MISSING_KEY"
        assert body["error"]["message"] == "API 密钥为必填项"

    def test_error_message_in_english(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "en-US"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["message"] == "API key is required"

    def test_language_switch_between_requests(self, client):
        resp_en = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "en"},
        )
        assert resp_en.json()["error"]["message"] == "API key is required"

        resp_zh = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "zh"},
        )
        assert resp_zh.json()["error"]["message"] == "API 密钥为必填项"

    def test_unsupported_language_falls_back_to_english(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "fr-FR"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["message"] == "API key is required"

    def test_quality_value_language_selection(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "", "provider": "openai"},
            headers={"Accept-Language": "fr;q=0.9,zh;q=0.8,en;q=0.7"},
        )
        assert resp.json()["error"]["message"] == "API 密钥为必填项"

    def test_provider_error_in_chinese(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "sk-test", "provider": "nonexistent"},
            headers={"Accept-Language": "zh"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_PROVIDER_UNKNOWN"
        assert body["error"]["message"] == "无法检测提供商，请手动选择"

    def test_provider_error_in_english(self, client):
        resp = client.post(
            "/api/check/single",
            json={"key": "sk-test", "provider": "nonexistent"},
            headers={"Accept-Language": "en"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["message"] == "Unable to detect provider, please select manually"
