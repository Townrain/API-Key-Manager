import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx

from .providers import PROVIDERS
from .validator import validate_keys


async def run_check(keys_file: str = "./data/keys.json",
                    results_file: str = "./data/check_results.json",
                    logs_dir: str = "./data/logs",
                    concurrency: int = 100,
                    timeout: int = 30,
                    proxy: str = None,
                    retry_failed: bool = True,
                    retry_count: int = 2) -> dict:
    results = await validate_keys(
        keys_file=keys_file,
        results_file=results_file,
        logs_dir=logs_dir,
        concurrency=concurrency,
        timeout=timeout,
        proxy=proxy
    )

    # Retry failed keys
    if retry_failed and results["summary"]["error"]["count"] > 0:
        for i in range(retry_count):
            error_keys = results["summary"]["error"]["keys"]
            if not error_keys:
                break

            retry_results = await validate_keys(
                keys_file=keys_file,
                results_file=results_file,
                logs_dir=logs_dir,
                concurrency=concurrency,
                timeout=timeout,
                proxy=proxy,
                status_filter="error"
            )

            # Merge results
            results["summary"]["valid"]["count"] += retry_results["summary"]["valid"]["count"]
            results["summary"]["invalid"]["count"] += retry_results["summary"]["invalid"]["count"]
            results["summary"]["error"]["count"] = retry_results["summary"]["error"]["count"]

    return results
