"""Supplementary tests for parser.py - import_keys function."""
import json
from pathlib import Path

import pytest

from key_manager.parser import import_keys, mask_key, validate_import_path


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

    def test_import_no_file_or_directory(self, tmp_data_dir):
        """Import with no file or directory returns error."""
        keys_file = tmp_data_dir / "keys.json"
        new, dupes, errors = import_keys(keys_file=str(keys_file))

        assert new == 0
        assert dupes == 0
        assert len(errors) > 0

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


class TestMaskKey:
    """Tests for mask_key function."""

    def test_mask_short_key(self):
        """Short keys are masked correctly."""
        assert mask_key("abc") == "abc"

    def test_mask_normal_key(self):
        """Normal keys show first 4 and last 4 chars."""
        result = mask_key("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "..." in result

    def test_mask_empty_key(self):
        """Empty key returns empty string."""
        assert mask_key("") == ""


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
