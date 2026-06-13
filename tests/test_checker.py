"""Unit tests for checker module."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch


def _make_keys_data(status="error", count=1):
    keys = {}
    for i in range(count):
        key = f"sk-test-{i:03d}"
        keys[key] = {
            "key_masked": key[:6] + "...000",
            "provider": "openai",
            "status": status,
            "sources": [],
            "checks": [],
            "tests": {},
        }
    return {"keys": keys}


def _write_keys(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_validate_result(valid=0, invalid=0, error=0):
    return {
        "run_at": "2024-01-01T00:00:00Z",
        "total": valid + invalid + error,
        "summary": {
            "valid": {"count": valid, "keys": [f"sk-valid-{i}" for i in range(valid)]},
            "invalid": {"count": invalid, "keys": [f"sk-invalid-{i}" for i in range(invalid)]},
            "error": {"count": error, "keys": [f"sk-error-{i}" for i in range(error)]},
        },
        "details": [],
        "by_provider": {},
    }


class TestRunCheck:
    """Tests for run_check function."""

    @pytest.mark.asyncio
    async def test_run_check_no_retry_needed(self, tmp_path):
        """All valid keys, no retry needed."""
        keys_data = _make_keys_data("valid", 2)
        keys_file = tmp_path / "keys.json"
        _write_keys(keys_file, keys_data)

        with patch("key_manager.checker.validate_keys", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = _make_validate_result(valid=2)

            from key_manager.checker import run_check
            results = await run_check(
                keys_file=str(keys_file),
                results_file=str(tmp_path / "results.json"),
                logs_dir=str(tmp_path / "logs"),
                retry_failed=True,
                retry_count=2,
            )

        assert mock_validate.call_count == 1  # Only initial check, no retry
        assert results["summary"]["valid"]["count"] == 2

    @pytest.mark.asyncio
    async def test_run_check_retry_errors(self, tmp_path):
        """Retries keys with error status."""
        keys_data = _make_keys_data("error", 2)
        keys_file = tmp_path / "keys.json"
        _write_keys(keys_file, keys_data)

        with patch("key_manager.checker.validate_keys", new_callable=AsyncMock) as mock_validate:
            # First call: 2 errors. Retry call: 1 valid, 1 error.
            mock_validate.side_effect = [
                _make_validate_result(error=2),
                _make_validate_result(valid=1, error=1),
                _make_validate_result(error=1),  # Second retry still has 1 error
            ]

            from key_manager.checker import run_check
            results = await run_check(
                keys_file=str(keys_file),
                results_file=str(tmp_path / "results.json"),
                logs_dir=str(tmp_path / "logs"),
                retry_failed=True,
                retry_count=2,
            )

        assert mock_validate.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_run_check_retry_disabled(self, tmp_path):
        """retry_failed=False skips retry."""
        keys_data = _make_keys_data("error", 1)
        keys_file = tmp_path / "keys.json"
        _write_keys(keys_file, keys_data)

        with patch("key_manager.checker.validate_keys", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = _make_validate_result(error=1)

            from key_manager.checker import run_check
            await run_check(
                keys_file=str(keys_file),
                results_file=str(tmp_path / "results.json"),
                logs_dir=str(tmp_path / "logs"),
                retry_failed=False,
                retry_count=2,
            )

        assert mock_validate.call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_run_check_merge_results(self, tmp_path):
        """Results are merged correctly after retry."""
        keys_data = _make_keys_data("error", 2)
        keys_file = tmp_path / "keys.json"
        _write_keys(keys_file, keys_data)

        with patch("key_manager.checker.validate_keys", new_callable=AsyncMock) as mock_validate:
            mock_validate.side_effect = [
                _make_validate_result(error=2),       # Initial: 2 errors
                _make_validate_result(valid=2),        # Retry: both fixed
            ]

            from key_manager.checker import run_check
            results = await run_check(
                keys_file=str(keys_file),
                results_file=str(tmp_path / "results.json"),
                logs_dir=str(tmp_path / "logs"),
                retry_failed=True,
                retry_count=1,
            )

        assert results["summary"]["valid"]["count"] == 2
