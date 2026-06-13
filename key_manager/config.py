import yaml
from pathlib import Path

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


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, user_config)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict, path: str = "config.yaml"):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
