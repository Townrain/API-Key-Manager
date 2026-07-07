import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from unittest.mock import patch

# Import shared helpers
from tests.helpers import (
    MockProvider,
    MockProviderWithTokenLimit,
    make_mock_provider as _make_mock_provider,
    make_key_info,
    make_keys_data_from_dict,
    make_keys_data_from_list,
    AsyncContextManagerMock,
)

# Import rate limit store for cleanup
from key_manager.web.middleware import _RATE_LIMIT_STORE

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory with required structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "input").mkdir()
    (data_dir / "cache").mkdir()
    (data_dir / "logs").mkdir()
    return data_dir


@pytest.fixture
def sample_keys_file(tmp_data_dir):
    """Create a sample keys.json file."""
    keys_file = tmp_data_dir / "keys.json"
    keys_data = {
        "keys": {
            "sk-test123456789": {
                "key": "sk-test123456789",
                "key_masked": "sk-tes...6789",
                "provider": "openai",
                "status": "unknown",
                "last_checked": None,
                "checks": [],
                "tests": {},
                "sources": [{"file": "test.json", "batch": "test"}]
            }
        },
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "last_updated": "2024-01-01T00:00:00Z"
        }
    }
    keys_file.write_text(json.dumps(keys_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return keys_file


@pytest.fixture
def sample_config(tmp_data_dir):
    """Create a sample config dictionary."""
    return {
        "scan": {
            "directories": [str(tmp_data_dir / "input")],
            "recursive": True,
        },
        "proxy": "",
        "check": {
            "interval_hours": 6,
            "timeout_seconds": 30,
            "concurrency": 100,
            "retry_failed": True,
            "retry_count": 2,
        },
        "test": {
            "token_test": True,
            "token_auto_detect": True,
            "token_steps": [1024, 4096, 16384],
            "token_max_manual": None,
            "concurrency_test": True,
            "concurrency_steps": [1, 5, 10],
            "concurrency_timeout_seconds": 120,
        },
        "storage": {
            "keys_file": str(tmp_data_dir / "keys.json"),
            "check_results_file": str(tmp_data_dir / "check_results.json"),
            "test_results_file": str(tmp_data_dir / "test_results.json"),
            "logs_dir": str(tmp_data_dir / "logs"),
        },
    }



@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    from unittest.mock import AsyncMock, MagicMock
    
    provider = MagicMock()
    provider.name = "test-provider"
    provider.base_url = "https://api.test.com/v1"
    provider.check_endpoint = "/models"
    provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
    provider.check = AsyncMock(return_value=MagicMock(
        valid=True,
        status_code=200,
        latency_ms=100.0,
        error=None,
        error_type=None,
        response_body='{"data": []}'
    ))
    provider.get_models = AsyncMock(return_value=["model-1", "model-2"])
    provider.test_token_limit = AsyncMock(return_value=MagicMock(
        max_tokens=16384,
        models=["model-1", "model-2"],
        error=None
    ))
    provider.test_concurrency = AsyncMock(return_value=MagicMock(
        max_concurrency=10,
        error=None
    ))
    provider.get_balance = AsyncMock(return_value=MagicMock(
        supported=True,
        balance=100.0,
        currency="USD",
        error=None
    ))
    return provider


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset global state between tests."""
    from pathlib import Path
    from key_manager.storage import clear_all_caches
    _RATE_LIMIT_STORE.clear()
    monkeypatch.delenv("KEY_MANAGER_SECRET", raising=False)
    monkeypatch.delenv("KEY_MANAGER_API_KEY", raising=False)
    Path("config.yaml").unlink(missing_ok=True)
    clear_all_caches()
    yield
    _RATE_LIMIT_STORE.clear()
    clear_all_caches()
# ── Shared helpers (not fixtures, used by fixture factories) ────────────

def make_config(tmp_path, *, api_key="test-api-key-12345", concurrency=10, timeout=10):
    """Build a standard test config dict pointing at tmp_path."""
    return {
        "storage": {
            "keys_file": str(tmp_path / "keys.json"),
            "check_results_file": str(tmp_path / "check_results.json"),
            "test_results_file": str(tmp_path / "test_results.json"),
            "logs_dir": str(tmp_path / "logs"),
        },
        "scan": {"directories": [str(tmp_path / "input")]},
        "proxy": "",
        "check": {"concurrency": concurrency, "timeout_seconds": timeout, "retry_failed": False, "retry_count": 0},
        "test": {
            "token_test": True, "token_steps": [1024, 4096],
            "concurrency_test": True, "concurrency_steps": [1, 5],
            "concurrency_timeout_seconds": 30,
        },
        "auth": {"api_key": api_key},
        "rate_limit": {"requests_per_minute": 0},
    }


def write_keys_file(path: Path, data: dict):
    """Write keys data to a JSON file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def make_keys_data(*, keys=None):
    """Build a minimal keys.json structure for testing.
    
    Args:
        keys: List of dicts with key, provider, status fields. 
              If None, creates a single default openai key.
    """
    return make_keys_data_from_list(keys)


# ── Shared fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    """FastAPI TestClient with standard test config and auth."""
    cfg = make_config(tmp_path)
    api_key = cfg.get("auth", {}).get("api_key", "")
    with patch("key_manager.web._app.config", cfg), patch("key_manager.web.middleware._config", cfg):
        from key_manager.web import app
        from fastapi.testclient import TestClient
        yield TestClient(app, headers={"Authorization": f"Bearer {api_key}"})


@pytest.fixture
def make_mock_provider():
    """Factory fixture: returns a function to create mock providers."""
    def _factory(name="openai", check_valid=True, models=None, balance=100.0):
        return _make_mock_provider(name=name, check_valid=check_valid, models=models, balance=balance)
    return _factory
