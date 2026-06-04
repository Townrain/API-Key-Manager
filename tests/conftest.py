import json
import os
import tempfile
from pathlib import Path

import pytest


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
def test_client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from web import app
    return TestClient(app)


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
def reset_environment():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
