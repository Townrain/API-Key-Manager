"""Unit tests for key_manager.parser module."""
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from key_manager.parser import (
    extract_batch_from_filename,
    import_keys,
    load_keys_file,
    mask_key,
    save_keys_file,
    validate_import_path,
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


# ---------------------------------------------------------------------------
# import_keys tests
# ---------------------------------------------------------------------------


class TestImportKeys:
    """Tests for import_keys function."""

    def test_import_from_file(self, tmp_data_dir):
        """Import keys from a JSON file."""
        # Create test file
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "test.json"
        test_file.write_text(json.dumps([
            {"key": "sk-test-key-1", "provider": "openai"},
            {"key": "sk-test-key-2", "provider": "anthropic"},
        ]), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(
            file_path=str(test_file),
            keys_file=str(keys_file)
        )

        assert new == 2
        assert dupes == 0
        assert errors == []

    def test_import_from_directory(self, tmp_data_dir):
        """Import keys from a directory."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)

        # Create multiple test files
        for i in range(3):
            test_file = input_dir / f"test{i}.json"
            test_file.write_text(json.dumps([
                {"key": f"sk-test-key-{i}", "provider": "openai"}
            ]), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(
            directory=str(input_dir),
            keys_file=str(keys_file)
        )

        assert new == 3
        assert dupes == 0
        assert errors == []

    def test_import_deduplication(self, tmp_data_dir):
        """Duplicate keys are counted correctly."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "test.json"

        # First import
        test_file.write_text(json.dumps([
            {"key": "sk-same-key", "provider": "openai"}
        ]), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new1, dupes1, _ = import_keys(file_path=str(test_file), keys_file=str(keys_file))
        assert new1 == 1
        assert dupes1 == 0

        # Second import with same key
        test_file.write_text(json.dumps([
            {"key": "sk-same-key", "provider": "openai"},
            {"key": "sk-new-key", "provider": "openai"}
        ]), encoding="utf-8")

        new2, dupes2, _ = import_keys(file_path=str(test_file), keys_file=str(keys_file))
        assert new2 == 1
        assert dupes2 == 1

    def test_import_file_not_found(self, tmp_data_dir):
        """Import from non-existent file returns error."""
        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(
            file_path="/nonexistent/file.json",
            keys_file=str(keys_file)
        )

        assert new == 0
        assert dupes == 0
        assert len(errors) > 0
        assert any("not found" in e.lower() or "不存在" in e for e in errors), f"Expected 'not found' error, got: {errors}"

    def test_import_directory_not_found(self, tmp_data_dir):
        """Import from non-existent directory returns error."""
        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(
            directory="/nonexistent/dir",
            keys_file=str(keys_file)
        )

        assert new == 0
        assert dupes == 0
        assert len(errors) > 0
        assert any("not found" in e.lower() or "不存在" in e for e in errors), f"Expected 'not found' error, got: {errors}"

    def test_import_no_file_or_directory(self, tmp_data_dir):
        """Import with no file or directory returns error."""
        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(keys_file=str(keys_file))

        assert new == 0
        assert dupes == 0
        assert len(errors) > 0
        assert any("specify" in e.lower() or "file" in e.lower() or "指定" in e for e in errors), f"Expected 'specify file' error, got: {errors}"

    def test_import_invalid_json(self, tmp_data_dir):
        """Import from invalid JSON file returns error."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "invalid.json"
        test_file.write_text("not valid json", encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(file_path=str(test_file), keys_file=str(keys_file))

        assert new == 0
        assert len(errors) > 0
        assert any("json" in e.lower() or "parse" in e.lower() or "解析" in e for e in errors), f"Expected JSON parse error, got: {errors}"

    def test_import_not_json_array(self, tmp_data_dir):
        """Import from JSON file that's not an array returns error."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "object.json"
        test_file.write_text(json.dumps({"key": "sk-test"}), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(file_path=str(test_file), keys_file=str(keys_file))

        assert new == 0
        assert len(errors) > 0
        assert any("array" in e.lower() or "list" in e.lower() or "数组" in e for e in errors), f"Expected 'not array' error, got: {errors}"

    def test_import_items_without_key_field(self, tmp_data_dir):
        """Import items without 'key' field are skipped."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "test.json"
        test_file.write_text(json.dumps([
            {"provider": "openai"},  # No 'key' field
            {"key": "sk-valid-key", "provider": "openai"},
        ]), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(file_path=str(test_file), keys_file=str(keys_file))

        assert new == 1  # Only the valid key

    def test_import_with_batch_label(self, tmp_data_dir):
        """Import with custom batch label."""
        input_dir = tmp_data_dir / "input"
        input_dir.mkdir(exist_ok=True)
        test_file = input_dir / "test.json"
        test_file.write_text(json.dumps([
            {"key": "sk-test-key", "provider": "openai"}
        ]), encoding="utf-8")

        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(
            file_path=str(test_file),
            batch="my-batch",
            keys_file=str(keys_file)
        )

        assert new == 1

        # Verify batch label in saved data
        with open(keys_file, "r") as f:
            data = json.load(f)
        assert data["keys"]["sk-test-key"]["sources"][0]["batch"] == "my-batch"


# ---------------------------------------------------------------------------
# validate_import_path tests
# ---------------------------------------------------------------------------


class TestValidateImportPath:
    """Tests for validate_import_path function."""

    def test_validate_allowed_path(self, tmp_data_dir):
        """Path within allowed directories returns Path object."""
        allowed_dir = tmp_data_dir / "input"
        allowed_dir.mkdir(exist_ok=True)
        test_file = allowed_dir / "test.json"
        test_file.write_text("[]", encoding="utf-8")

        result = validate_import_path(str(test_file), [str(allowed_dir)])
        assert isinstance(result, Path)

    def test_validate_disallowed_path(self, tmp_data_dir):
        """Path outside allowed directories raises error."""
        from key_manager.errors import ValidationError
        with pytest.raises(ValidationError):
            validate_import_path("/etc/passwd", [str(tmp_data_dir / "input")])
