import asyncio
from datetime import datetime, timezone

import httpx

from .providers import PROVIDERS
from .logger import KeyLogger
from .storage import KeyStore
from .config import load_config

async def validate_keys(keys_file: str = "./data/keys.json",
                        results_file: str = "./data/check_results.json",
                        logs_dir: str = "./data/logs",
                        concurrency: int = 100,
                        timeout: int = 30,
                        proxy: str = None,
                        provider_filter: str = None,
                        status_filter: str = None,
                        single_key: str = None,
                        progress_callback=None,
                        config: dict = None) -> dict:
    logger = KeyLogger(logs_dir, "check")

    # Use KeyStore for encrypted storage
    cfg = config or load_config()
    store = KeyStore(keys_file, cfg)
    data = store.load()

    keys_to_check = []
    for key, info in data["keys"].items():
        if single_key and key != single_key:
            continue
        if provider_filter and info["provider"].lower() != provider_filter.lower():
            continue
        if status_filter and info["status"] != status_filter:
            continue
        keys_to_check.append((key, info))

    total = len(keys_to_check)
    results = {
        "run_at": datetime.now(timezone.utc).isoformat() + "Z",
        "total": total,
        "summary": {
            "valid": {"count": 0, "keys": []},
            "invalid": {"count": 0, "keys": []},
            "error": {"count": 0, "keys": []}
        },
        "details": [],
        "by_provider": {}
    }

    # Initialize progress
    if progress_callback:
        progress_callback(0, total)

    semaphore = asyncio.Semaphore(concurrency)
    completed_count = 0

    async def check_one(client: httpx.AsyncClient, key: str, info: dict):
        nonlocal completed_count
        async with semaphore:
            provider_name = info["provider"].lower()
            provider = PROVIDERS.get(provider_name)
            if not provider:
                from key_manager.providers.base import CheckResult
                result = CheckResult(valid=False, status_code=None, latency_ms=0, error=f"unknown provider: {provider_name}")
            else:
                result = await provider.check(client, key)

                # Get balance if provider supports it and key is valid
                balance_info = None
                if result.valid and hasattr(provider, 'get_balance'):
                    try:
                        balance_result = await provider.get_balance(client, key)
                        if balance_result.supported and balance_result.balance is not None:
                            balance_info = {
                                "balance": balance_result.balance,
                                "currency": balance_result.currency
                            }
                    except Exception:
                        pass  # Balance fetch failed, continue without it

                # Determine error_type based on status code and error message
                error_type = None
                if not result.valid:
                    error_msg = getattr(result, 'error', None) or ""
                    status_code = result.status_code
                    if status_code in (401, 403):
                        error_type = "invalid_key"
                    elif status_code == 429:
                        error_type = "rate_limited"
                    elif status_code == 402:
                        error_type = "insufficient_balance"
                    elif status_code and status_code >= 500:
                        error_type = "server_error"
                    elif any(kw in error_msg.lower() for kw in ["balance", "quota"]):
                        error_type = "insufficient_balance"
                    else:
                        error_type = "unknown"

                # Store balance and error_type in result for later use
                result.balance = balance_info
                result.error_type = error_type

            completed_count += 1
            if progress_callback:
                progress_callback(completed_count, total)

            return key, info, result

    async with httpx.AsyncClient(timeout=timeout, proxy=proxy, follow_redirects=False) as client:
        tasks = [check_one(client, k, i) for k, i in keys_to_check]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

    for item in completed:
        if isinstance(item, Exception):
            # Handle exceptions from gather
            logger.log("CHECK", "unknown", "unknown", "ERROR", str(item), 0)
            continue

        key, info, result = item
        key_masked = info["key_masked"]
        provider = info["provider"]

        # Ensure result has error field
        error_msg = getattr(result, 'error', None) or None

        if result.valid:
            status = "valid"
            results["summary"]["valid"]["count"] += 1
            results["summary"]["valid"]["keys"].append(key_masked)
        elif result.status_code in (401, 403):
            status = "invalid"
            # Make sure we have an error message for invalid keys
            if not error_msg:
                error_msg = "invalid key"
            results["summary"]["invalid"]["count"] += 1
            results["summary"]["invalid"]["keys"].append(key_masked)
        else:
            status = "error"
            # Make sure we have an error message for errors
            if not error_msg:
                if result.status_code:
                    error_msg = f"HTTP {result.status_code}"
                else:
                    error_msg = "connection failed"
            results["summary"]["error"]["count"] += 1
            results["summary"]["error"]["keys"].append(key_masked)

        detail = error_msg or str(result.status_code)
        logger.log("CHECK", provider, key_masked, status.upper(), detail, result.latency_ms / 1000)

        results["details"].append({
            "key_masked": key_masked,
            "provider": provider,
            "status": status,
            "code": result.status_code,
            "latency_ms": result.latency_ms,
            "error": error_msg,
            "error_type": getattr(result, 'error_type', None),
            "balance": getattr(result, 'balance', None)
        })

        if provider not in results["by_provider"]:
            results["by_provider"][provider] = {"valid": 0, "invalid": 0, "error": 0}
        results["by_provider"][provider][status] += 1

        data["keys"][key]["status"] = status
        data["keys"][key]["checks"].append({
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "status": status,
            "status_code": result.status_code,
            "latency_ms": result.latency_ms,
            "error": error_msg,
            "error_type": getattr(result, 'error_type', None),
            "balance": getattr(result, 'balance', None)
        })
        data["keys"][key]["last_checked"] = datetime.now(timezone.utc).isoformat() + "Z"

    # Use KeyStore for encrypted storage
    store.save(data)

    # Results file is not sensitive, write directly
    with open(results_file, "w", encoding="utf-8") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.flush()
    return results
