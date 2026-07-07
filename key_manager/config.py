import copy
import logging
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "scan": {
        "directories": ["./data/input"],
        "recursive": True,
    },
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
        "token_steps": [1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576],
        "token_max_manual": None,
        "concurrency_test": True,
        "concurrency_steps": [1, 5, 10, 20, 50, 100],
        "concurrency_timeout_seconds": 120,
    },
    "storage": {
        "keys_file": "./data/keys.json",
        "check_results_file": "./data/check_results.json",
        "test_results_file": "./data/test_results.json",
        "logs_dir": "./data/logs",
        "encrypted": True,
    },
    "auth": {
        "api_key": "",
    },
    "rate_limit": {
        "requests_per_minute": 60,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _validate_config(config: dict) -> dict:
    """Validate config values and warn about unknown keys."""
    valid_keys = set(DEFAULT_CONFIG.keys())
    unknown_keys = set(config.keys()) - valid_keys
    if unknown_keys:
        logger.warning(f"Unknown config keys (ignored): {unknown_keys}")

    # Validate numeric values
    check_config = config.get("check", {})
    if check_config.get("concurrency", 100) < 1:
        logger.warning("check.concurrency must be >= 1, using default")
        check_config["concurrency"] = 100
    if check_config.get("timeout_seconds", 30) < 1:
        logger.warning("check.timeout_seconds must be >= 1, using default")
        check_config["timeout_seconds"] = 30

    rate_limit = config.get("rate_limit", {})
    if rate_limit.get("requests_per_minute", 60) < 0:
        logger.warning("rate_limit.requests_per_minute must be >= 0, using default")
        rate_limit["requests_per_minute"] = 60

    return config


def _copy_example_config(config_path: Path):
    """Copy bundled config.yaml.example to config.yaml on first run."""
    if getattr(sys, "frozen", False):
        sample = Path(sys._MEIPASS) / "config.yaml.example"
    else:
        sample = Path("config.yaml.example")
    if sample.exists():
        try:
            config_path.write_bytes(sample.read_bytes())
            logger.info(f"Created default config at {config_path}")
        except OSError:
            pass


def load_config(path: str = "config.yaml") -> dict:
    # PyInstaller exe: resolve path next to the exe, auto-create from example
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.argv[0]).parent
        path = str(exe_dir / "config.yaml")

    config_path = Path(path)
    if not config_path.exists():
        _copy_example_config(config_path)

    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            if not isinstance(user_config, dict):
                logger.warning(f"Config file {path} is not a dict, using defaults")
                return copy.deepcopy(DEFAULT_CONFIG)
            config = _deep_merge(DEFAULT_CONFIG, user_config)
            return _validate_config(config)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config file {path}: {e}")
            return copy.deepcopy(DEFAULT_CONFIG)
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")
            return copy.deepcopy(DEFAULT_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict, path: str = "config.yaml"):
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        logger.error(f"Failed to save config file {path}: {e}")
