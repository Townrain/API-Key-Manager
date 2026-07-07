import json
import logging
from datetime import datetime
from pathlib import Path


def _ensure_logs_dir(logs_dir: str = "./data/logs") -> Path:
    """Create and return the logs directory."""
    d = Path(logs_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


class KeyLogger:
    """Structured logger with date-based file rotation."""

    def __init__(self, logs_dir: str, category: str):
        self.logs_dir = _ensure_logs_dir(logs_dir)
        self.category = category
        self.logger = logging.getLogger(f"keymanager.{category}")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            self._setup_file_handler()

    def _setup_file_handler(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{self.category}_{date_str}.log"

        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log(self, action: str, provider: str, key_masked: str,
            status: str, detail: str = "", latency: float = 0.0):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider_padded = provider.ljust(10)
        line = f"[{timestamp}] [{action}] [{provider_padded}] {key_masked} -> {status}"
        if detail:
            line += f" ({detail}, {latency:.2f}s)"
        self.logger.info(line)

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()


class ProjectLogger:
    """Main project logger that logs all operations."""

    def __init__(self, logs_dir: str = "./data/logs"):
        self.logs_dir = _ensure_logs_dir(logs_dir)
        self._setup_loggers()

    def _setup_loggers(self):
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Main log - all operations
        self.main_logger = self._create_logger(
            "main",
            self.logs_dir / f"main_{date_str}.log"
        )

        # JSON log for structured data
        self.json_log_file = self.logs_dir / f"operations_{date_str}.jsonl"

    def _create_logger(self, name: str, log_file: Path) -> logging.Logger:
        logger = logging.getLogger(f"project.{name}")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def _write_json_log(self, operation: str, data: dict):
        """Write structured JSON log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            **data
        }
        with open(self.json_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_import(self, filename: str, new_keys: int, duplicates: int, errors: list):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [IMPORT] {filename} -> new={new_keys}, dupes={duplicates}"
        if errors:
            line += f", errors={len(errors)}"
        self.main_logger.info(line)
        self._write_json_log("import", {
            "filename": filename,
            "new_keys": new_keys,
            "duplicates": duplicates,
            "errors": errors
        })

    def log_check(self, provider: str, key_masked: str, status: str,
                  status_code: int | None = None, latency_ms: float = 0, error: str = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider_padded = provider.ljust(10)
        line = f"[{timestamp}] [CHECK  ] [{provider_padded}] {key_masked} -> {status}"
        if status_code:
            line += f" (code={status_code}, {latency_ms:.0f}ms)"
        if error:
            line += f" error={error}"
        self.main_logger.info(line)
        self._write_json_log("check", {
            "provider": provider,
            "key_masked": key_masked,
            "status": status,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "error": error
        })

    def log_test(self, provider: str, key_masked: str, max_tokens: int | None,
                 max_concurrency: int | None, models_count: int = 0):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider_padded = provider.ljust(10)
        line = f"[{timestamp}] [TEST   ] [{provider_padded}] {key_masked} -> tokens={max_tokens}, conc={max_concurrency}, models={models_count}"
        self.main_logger.info(line)
        self._write_json_log("test", {
            "provider": provider,
            "key_masked": key_masked,
            "max_tokens": max_tokens,
            "max_concurrency": max_concurrency,
            "models_count": models_count
        })

    def log_manual_check(self, key_masked: str, provider: str, status: str,
                         check_type: str = "fast", error: str = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [MANUAL ] [{provider.ljust(10)}] {key_masked} -> {status} ({check_type})"
        if error:
            line += f" error={error}"
        self.main_logger.info(line)
        self._write_json_log("manual_check", {
            "key_masked": key_masked,
            "provider": provider,
            "status": status,
            "check_type": check_type,
            "error": error
        })

    def log_export(self, count: int, format: str = "txt"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [EXPORT ] Exported {count} keys as {format}"
        self.main_logger.info(line)
        self._write_json_log("export", {"count": count, "format": format})

    def log_web_action(self, action: str, detail: str = ""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [WEB    ] {action}"
        if detail:
            line += f" - {detail}"
        self.main_logger.info(line)

    def get_recent_logs(self, lines: int = 100) -> list:
        """Get recent log entries from main log file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"main_{date_str}.log"

        if not log_file.exists():
            return []

        with open(log_file, encoding="utf-8") as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]

    def get_operations_log(self, limit: int = 50) -> list:
        """Get structured operations log."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        json_file = self.logs_dir / f"operations_{date_str}.jsonl"

        if not json_file.exists():
            return []

        entries = []
        with open(json_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except (json.JSONDecodeError, ValueError):
                    pass  # Skip malformed lines
        return entries[-limit:]

    def get_log_files(self) -> list:
        """Get list of all log files."""
        files = []
        for f in sorted(self.logs_dir.glob("*.log"), reverse=True):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        for f in sorted(self.logs_dir.glob("*.jsonl"), reverse=True):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return files


    def clear_main_log(self, date: str = None) -> dict:
        """Clear main log file for specified date (default: today).

        Args:
            date: Date string in YYYY-MM-DD format (default: today)

        Returns:
            dict with 'success', 'date', 'deleted_lines' keys
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        log_file = self.logs_dir / f"main_{date}.log"
        if not log_file.exists():
            return {"success": False, "date": date, "deleted_lines": 0, "error": "Log file not found"}

        # Count lines before clearing
        with open(log_file, encoding="utf-8") as f:
            lines_count = sum(1 for _ in f)

        # Clear the file
        log_file.write_text("", encoding="utf-8")

        return {"success": True, "date": date, "deleted_lines": lines_count}


# Global logger instance
project_logger = ProjectLogger()
