"""Tests for logger module."""
import json
import logging
from pathlib import Path

import pytest

from key_manager.logger import KeyLogger, ProjectLogger


@pytest.fixture(autouse=True)
def cleanup_loggers():
    """Clean up loggers after each test to avoid handler conflicts."""
    yield
    # Remove all handlers from test loggers
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("keymanager.") or name.startswith("project."):
            logger = logging.getLogger(name)
            logger.handlers.clear()


class TestKeyLogger:
    """Tests for KeyLogger class."""

    def test_init_creates_log_dir(self, tmp_path):
        """Creates log directory if not exists."""
        logs_dir = tmp_path / "logs"
        logger = KeyLogger(str(logs_dir), "test_init_dir")
        assert logs_dir.exists()

    def test_init_creates_log_file(self, tmp_path):
        """Creates log file on first write."""
        logs_dir = tmp_path / "logs"
        logger = KeyLogger(str(logs_dir), "test_init_file")
        # Need to log something to trigger file creation
        logger.log("TEST", "provider", "key", "OK")
        logger.flush()
        log_files = list(logs_dir.glob("test_init_file_*.log"))
        assert len(log_files) == 1

    def test_log_writes_entry(self, tmp_path):
        """Writes formatted log entry."""
        logs_dir = tmp_path / "logs"
        logger = KeyLogger(str(logs_dir), "test_write")
        logger.log("CHECK", "openai", "sk-tes...6789", "VALID", "code=200", 0.15)
        logger.flush()

        log_files = list(logs_dir.glob("test_write_*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "[CHECK]" in content
        assert "openai" in content
        assert "sk-tes...6789" in content
        assert "VALID" in content

    def test_log_without_detail(self, tmp_path):
        """Logs entry without detail and latency."""
        logs_dir = tmp_path / "logs"
        logger = KeyLogger(str(logs_dir), "test_no_detail")
        logger.log("IMPORT", "unknown", "sk-xxx", "OK")
        logger.flush()

        log_files = list(logs_dir.glob("test_no_detail_*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "IMPORT" in content
        assert "OK" in content

    def test_flush(self, tmp_path):
        """Flushes all handlers."""
        logs_dir = tmp_path / "logs"
        logger = KeyLogger(str(logs_dir), "test_flush")
        # Should not raise
        logger.flush()


class TestProjectLogger:
    """Tests for ProjectLogger class."""

    def test_init_creates_log_dir(self, tmp_path):
        """Creates log directory if not exists."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        assert logs_dir.exists()

    def test_init_creates_main_log(self, tmp_path):
        """Creates main log file on first write."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        # Trigger log write
        logger.log_web_action("test")
        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) == 1

    def test_log_import(self, tmp_path):
        """Logs import operation."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_import("test.json", 5, 2, ["error1"])

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "IMPORT" in content
        assert "test.json" in content
        assert "new=5" in content
        assert "dupes=2" in content

    def test_log_import_writes_json(self, tmp_path):
        """Writes structured JSON log for import."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_import("test.json", 5, 2, [])

        json_files = list(logs_dir.glob("operations_*.jsonl"))
        assert len(json_files) == 1
        lines = json_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["operation"] == "import"
        assert entry["filename"] == "test.json"
        assert entry["new_keys"] == 5

    def test_log_check(self, tmp_path):
        """Logs check operation."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_check("openai", "sk-tes...6789", "valid", 200, 150.5)

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "CHECK" in content
        assert "openai" in content
        assert "valid" in content

    def test_log_check_with_error(self, tmp_path):
        """Logs check operation with error."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_check("openai", "sk-tes...6789", "invalid", 401, 100.0, "Invalid API key")

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "error=Invalid API key" in content

    def test_log_test(self, tmp_path):
        """Logs test operation."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_test("openai", "sk-tes...6789", 16384, 10, 5)

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "TEST" in content
        assert "tokens=16384" in content
        assert "conc=10" in content
        assert "models=5" in content

    def test_log_manual_check(self, tmp_path):
        """Logs manual check operation."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_manual_check("sk-tes...6789", "openai", "valid", "fast")

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "MANUAL" in content
        assert "fast" in content

    def test_log_export(self, tmp_path):
        """Logs export operation."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_export(10, "txt")

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "EXPORT" in content
        assert "10" in content

    def test_log_web_action(self, tmp_path):
        """Logs web action."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_web_action("import", "batch: 5 new")

        log_files = list(logs_dir.glob("main_*.log"))
        assert len(log_files) >= 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "WEB" in content
        assert "import" in content
        assert "batch: 5 new" in content

    def test_get_recent_logs(self, tmp_path):
        """Gets recent log entries."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_web_action("test1")
        logger.log_web_action("test2")
        logger.log_web_action("test3")

        logs = logger.get_recent_logs(2)
        assert len(logs) == 2
        assert "test2" in logs[0]
        assert "test3" in logs[1]

    def test_get_recent_logs_empty(self, tmp_path):
        """Returns empty list when no logs."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        # Close handlers to release file locks on Windows
        for handler in logger.main_logger.handlers:
            handler.close()
            logger.main_logger.removeHandler(handler)
        # Delete the main log file
        for f in logs_dir.glob("main_*.log"):
            f.unlink()
        logs = logger.get_recent_logs()
        assert logs == []
    def test_get_operations_log(self, tmp_path):
        """Gets structured operations log."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        logger.log_import("test.json", 5, 2, [])
        logger.log_check("openai", "sk-xxx", "valid")

        ops = logger.get_operations_log()
        assert len(ops) == 2
        assert ops[0]["operation"] == "import"
        assert ops[1]["operation"] == "check"

    def test_get_operations_log_empty(self, tmp_path):
        """Returns empty list when no operations."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        # Delete the jsonl file
        for f in logs_dir.glob("operations_*.jsonl"):
            f.unlink()
        ops = logger.get_operations_log()
        assert ops == []

    def test_get_log_files(self, tmp_path):
        """Gets list of log files."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        # Use log_import which writes to both main log and JSONL
        logger.log_import("test.json", 5, 2, [])

        files = logger.get_log_files()
        assert len(files) >= 1
        # Should have main log and operations jsonl
        file_names = [f["name"] for f in files]
        assert any("main_" in name for name in file_names)
        assert any("operations_" in name for name in file_names)
    def test_get_log_files_empty(self, tmp_path):
        """Returns empty list when no log files."""
        logs_dir = tmp_path / "logs"
        logger = ProjectLogger(str(logs_dir))
        # Close handlers to release file locks on Windows
        for handler in logger.main_logger.handlers:
            handler.close()
            logger.main_logger.removeHandler(handler)
        # Delete all log files
        for f in logs_dir.glob("*"):
            if f.is_file():
                f.unlink()
        files = logger.get_log_files()
        assert files == []
