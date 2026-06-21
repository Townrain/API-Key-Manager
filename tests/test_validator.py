import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.validator import validate_keys

os.environ.setdefault("KEY_MANAGER_SECRET", "test-secret-for-validator")

def _make_keys_data(keys: dict) -> dict:
    return {
        "keys": keys,
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "last_updated": "2024-01-01T00:00:00Z",
        },
    }


def _make_key_info(key: str, provider: str, status: str = "unknown") -> dict:
    return {
        "key": key,
        "key_masked": key[:6] + "..." + key[-4:],
        "provider": provider,
        "status": status,
        "last_checked": None,
        "checks": [],
        "tests": {},
        "sources": [{"file": "test.json", "batch": "test"}],
    }


@pytest.fixture
def keys_file(tmp_path):
    f = tmp_path / "keys.json"
    return str(f)


@pytest.fixture
def results_file(tmp_path):
    f = tmp_path / "results.json"
    return str(f)


@pytest.fixture
def logs_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return str(d)


class AsyncContextManagerMock(MagicMock):
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


async def test_validate_keys_all_valid(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-valid1": _make_key_info("sk-valid1", "openai"),
        "sk-valid2": _make_key_info("sk-valid2", "openai"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()
    mock_provider.check = AsyncMock(return_value=MagicMock(
        valid=True,
        status_code=200,
        latency_ms=150.0,
        error=None,
        error_type=None,
        balance=None,
    ))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
            )

    assert result["total"] == 2
    assert result["summary"]["valid"]["count"] == 2
    assert result["summary"]["invalid"]["count"] == 0
    assert result["summary"]["error"]["count"] == 0
    assert len(result["details"]) == 2
    assert all(d["status"] == "valid" for d in result["details"])
    assert mock_provider.check.await_count == 2


async def test_validate_keys_invalid(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-invalid": _make_key_info("sk-invalid", "openai"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()
    mock_provider.check = AsyncMock(return_value=MagicMock(
        valid=False,
        status_code=401,
        latency_ms=50.0,
        error="invalid key",
        error_type="invalid_key",
        balance=None,
    ))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
            )

    assert result["total"] == 1
    assert result["summary"]["invalid"]["count"] == 1
    detail = result["details"][0]
    assert detail["status"] == "invalid"
    assert detail["error_type"] == "invalid_key"
    assert detail["error"] == "invalid key"


async def test_validate_keys_error(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-err": _make_key_info("sk-err", "openai"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()
    mock_provider.check = AsyncMock(return_value=MagicMock(
        valid=False,
        status_code=500,
        latency_ms=30.0,
        error="server error",
        error_type="server_error",
        balance=None,
    ))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
            )

    assert result["total"] == 1
    assert result["summary"]["error"]["count"] == 1
    detail = result["details"][0]
    assert detail["status"] == "error"
    assert detail["code"] == 500


async def test_validate_keys_rate_limited(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-rate": _make_key_info("sk-rate", "openai"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()
    mock_provider.check = AsyncMock(return_value=MagicMock(
        valid=False,
        status_code=429,
        latency_ms=20.0,
        error="rate limited",
        error_type="rate_limited",
        balance=None,
    ))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
            )

    assert result["total"] == 1
    assert result["summary"]["error"]["count"] == 1
    detail = result["details"][0]
    assert detail["status"] == "error"
    assert detail["error_type"] == "rate_limited"
    assert detail["code"] == 429


async def test_validate_keys_provider_filter(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-openai": _make_key_info("sk-openai", "openai"),
        "sk-anthropic": _make_key_info("sk-anthropic", "anthropic"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_openai = MagicMock()
    mock_openai.check = AsyncMock(return_value=MagicMock(
        valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None, balance=None,
    ))
    mock_anthropic = MagicMock()
    mock_anthropic.check = AsyncMock(return_value=MagicMock(
        valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None, balance=None,
    ))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict(
            "key_manager.validator.PROVIDERS",
            {"openai": mock_openai, "anthropic": mock_anthropic},
            clear=True,
        ):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
                provider_filter="openai",
            )

    assert result["total"] == 1
    assert mock_openai.check.await_count == 1
    assert mock_anthropic.check.await_count == 0
    assert result["details"][0]["provider"] == "openai"


async def test_validate_keys_progress_callback(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        "sk-1": _make_key_info("sk-1", "openai"),
        "sk-2": _make_key_info("sk-2", "openai"),
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()
    mock_provider.check = AsyncMock(return_value=MagicMock(
        valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None, balance=None,
    ))

    calls = []

    def callback(done, total):
        calls.append((done, total))

    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=10,
                progress_callback=callback,
            )

    assert result["total"] == 2
    assert calls[0] == (0, 2)
    assert calls[-1] == (2, 2)
    assert len(calls) == 3  # 0, 1, 2


async def test_validate_keys_concurrency(keys_file, results_file, logs_dir):
    data = _make_keys_data({
        f"sk-{i}": _make_key_info(f"sk-{i}", "openai")
        for i in range(5)
    })
    with open(keys_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    mock_client = AsyncContextManagerMock()
    mock_provider = MagicMock()

    async def slow_check(*args, **kwargs):
        import asyncio
        await asyncio.sleep(0.05)
        return MagicMock(
            valid=True, status_code=200, latency_ms=100.0, error=None, error_type=None, balance=None,
        )

    mock_provider.check = AsyncMock(side_effect=slow_check)

    import asyncio

    start = datetime.utcnow()
    with patch("key_manager.validator.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("key_manager.validator.PROVIDERS", {"openai": mock_provider}, clear=True):
            result = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=2,
            )
    elapsed = (datetime.utcnow() - start).total_seconds()

    assert result["total"] == 5
    # With concurrency=2 and 5 tasks each taking ~0.05s, sequential would be 0.25s,
    # concurrent should be ~0.15s (3 batches). Allow generous margin.
    assert elapsed >= 0.10
    assert mock_provider.check.await_count == 5


# ---------------------------------------------------------------------------
# Supplementary tests from test_validator_supplement.py
# ---------------------------------------------------------------------------


@pytest.fixture
def validator_keys_file(tmp_data_dir):
    """Create a keys file for validator tests."""
    keys_file = tmp_data_dir / "keys.json"
    keys_data = {
        "keys": {
            "sk-valid-key-1": {
                "key_masked": "sk-valid...ey-1",
                "provider": "openai",
                "status": "valid",
                "checks": [],
                "tests": {},
                "sources": []
            },
            "sk-invalid-key-2": {
                "key_masked": "sk-inva...ey-2",
                "provider": "anthropic",
                "status": "invalid",
                "checks": [],
                "tests": {},
                "sources": []
            },
            "sk-unknown-key-3": {
                "key_masked": "sk-unkn...ey-3",
                "provider": "unknown",
                "status": "unknown",
                "checks": [],
                "tests": {},
                "sources": []
            }
        }
    }
    keys_file.write_text(json.dumps(keys_data, indent=2), encoding="utf-8")
    return keys_file


class TestValidateKeysSupplement:
    """Supplementary tests for validate_keys function."""

    async def test_validate_all_keys(self, tmp_data_dir, validator_keys_file):
        """Validate all keys in file."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir
            )

        assert results["total"] == 3
        assert results["summary"]["valid"]["count"] == 2  # 2 valid keys (unknown provider causes error)

    async def test_validate_with_provider_filter(self, tmp_data_dir, validator_keys_file):
        """Filter keys by provider."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                provider_filter="openai"
            )

        assert results["total"] == 1

    async def test_validate_with_status_filter(self, tmp_data_dir, validator_keys_file):
        """Filter keys by status."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                status_filter="valid"
            )

        assert results["total"] == 1

    async def test_validate_single_key(self, tmp_data_dir, validator_keys_file):
        """Validate a single specific key."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-valid-key-1"
            )

        assert results["total"] == 1

    async def test_validate_with_progress_callback(self, tmp_data_dir, validator_keys_file):
        """Progress callback is called."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        mock_provider = MagicMock()
        mock_provider.check = AsyncMock(return_value=MagicMock(
            valid=True, status_code=200, latency_ms=100.0,
            error=None, error_type=None, balance=None
        ))
        mock_provider.get_balance = AsyncMock(return_value=MagicMock(
            supported=False, balance=None, currency="USD", error=None
        ))

        with patch("key_manager.validator.PROVIDERS", {"openai": mock_provider, "anthropic": mock_provider}):
            await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                progress_callback=progress_callback
            )

        assert len(progress_calls) >= 2
        assert progress_calls[0] == (0, 3)
        assert progress_calls[-1] == (3, 3)

    async def test_validate_unknown_provider(self, tmp_data_dir, validator_keys_file):
        """Unknown provider gets error result."""
        results_file = str(tmp_data_dir / "results.json")
        logs_dir = str(tmp_data_dir / "logs")

        with patch("key_manager.validator.PROVIDERS", {}):
            results = await validate_keys(
                keys_file=str(validator_keys_file),
                results_file=results_file,
                logs_dir=logs_dir,
                single_key="sk-unknown-key-3"
            )

        assert results["total"] == 1
        assert results["details"][0]["status"] == "error"