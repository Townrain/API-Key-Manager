"""Unit tests for key_manager.parser module."""
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from key_manager.parser import (
    extract_batch_from_filename,
    load_keys_file,
    mask_key,
    save_keys_file,
)


# ---------------------------------------------------------------------------
# mask_key tests
# ---------------------------------------------------------------------------

class TestMaskKey:
    """Tests for the mask_key function."""

    def test_mask_key_long(self):
        """Long key (>10 chars) should show first 6 and last 4."""
        result = mask_key("sk-123456789012345")
        assert result == "sk-123...2345"

    def test_mask_key_short(self):
        """Keys with 10 or fewer characters are returned unchanged."""
        assert mask_key("short") == "short"
        assert mask_key("1234567890") == "1234567890"
        assert mask_key("a") == "a"

    def test_mask_key_empty(self):
        """Empty string should return empty string."""
        assert mask_key("") == ""

    def test_mask_key_exactly_10(self):
        """Exactly 10 characters should be returned as-is (boundary)."""
        key = "sk-abcdefg"  # 10 chars
        assert len(key) == 10
        assert mask_key(key) == key

    def test_mask_key_11_chars(self):
        """11 characters should be masked."""
        key = "sk-abcdefghi"  # 11 chars
        result = mask_key(key)
        assert result == "sk-abc...fghi"


# ---------------------------------------------------------------------------
# load_keys_file tests
# ---------------------------------------------------------------------------

class TestLoadKeysFile:
    """Tests for the load_keys_file function."""

    def test_load_keys_file_exists(self, tmp_path):
        """Should load and return JSON content from an existing file."""
        keys_file = tmp_path / "keys.json"
        data = {
            "version": "1.0",
            "keys": {"sk-test12345": {"provider": "openai"}},
            "imports": [],
        }
        keys_file.write_text(json.dumps(data), encoding="utf-8")

        result = load_keys_file(str(keys_file))

        assert result["version"] == "1.0"
        assert "sk-test12345" in result["keys"]
        assert result["keys"]["sk-test12345"]["provider"] == "openai"

    def test_load_keys_file_missing(self, tmp_path):
        """Missing file should return a default structure."""
        missing = tmp_path / "nonexistent.json"

        result = load_keys_file(str(missing))

        assert result["version"] == "1.0"
        assert result["imports"] == []
        assert result["keys"] == {}
        assert "updated_at" in result


# ---------------------------------------------------------------------------
# save_keys_file tests
# ---------------------------------------------------------------------------

class TestSaveKeysFile:
    """Tests for the save_keys_file function."""

    def test_save_keys_file(self, tmp_path):
        """Should write valid JSON with an updated_at timestamp."""
        keys_file = tmp_path / "keys.json"
        data = {
            "version": "1.0",
            "keys": {},
            "imports": [],
        }

        save_keys_file(data, str(keys_file))

        assert keys_file.exists()
        content = json.loads(keys_file.read_text(encoding="utf-8"))
        assert "updated_at" in content
        # Verify updated_at is a valid ISO timestamp
        datetime.fromisoformat(content["updated_at"].rstrip("Z"))

    def test_save_keys_file_preserves_content(self, tmp_path):
        """Saved file should contain all keys from the original dict."""
        keys_file = tmp_path / "keys.json"
        data = {
            "version": "1.0",
            "keys": {"sk-abc": {"provider": "openai"}},
            "imports": [{"file": "test.json"}],
        }

        save_keys_file(data, str(keys_file))
        loaded = json.loads(keys_file.read_text(encoding="utf-8"))

        assert loaded["version"] == "1.0"
        assert "sk-abc" in loaded["keys"]
        assert len(loaded["imports"]) == 1


# ---------------------------------------------------------------------------
# extract_batch_from_filename tests
# ---------------------------------------------------------------------------

class TestExtractBatchFromFilename:
    """Tests for the extract_batch_from_filename function."""

    def test_extract_batch_from_filename_with_date(self):
        """Should extract YYYY-MM-DD pattern from the filename."""
        assert extract_batch_from_filename("keys_2024-06-15.json") == "2024-06-15"
        assert extract_batch_from_filename("batch-2023-12-31-import.json") == "2023-12-31"
        assert extract_batch_from_filename("2025-01-01.json") == "2025-01-01"

    def test_extract_batch_from_filename_no_date(self):
        """Without a date pattern, should return today's date."""
        today = datetime.now().strftime("%Y-%m-%d")
        assert extract_batch_from_filename("keys.json") == today
        assert extract_batch_from_filename("import_batch.json") == today

    def test_extract_batch_from_filename_multiple_dates(self):
        """Should return the first date pattern found."""
        assert extract_batch_from_filename("2024-01-01_to_2024-12-31.json") == "2024-01-01"
