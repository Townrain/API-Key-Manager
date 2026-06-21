from datetime import datetime, timezone

import httpx

from .config import load_config
from .logger import KeyLogger
from .providers import PROVIDERS
from .storage import KeyStore


async def run_test(keys_file: str = "./data/keys.json",
                   results_file: str = "./data/test_results.json",
                   logs_dir: str = "./data/logs",
                   timeout: int = 30,
                   proxy: str = None,
                   token_test: bool = True,
                   concurrency_test: bool = True,
                   token_steps: list[int] = None,
                   concurrency_steps: list[int] = None,
                   provider_filter: str = None,
                   single_key: str = None,
                   progress_callback=None,
                   config: dict = None) -> dict:
    # Reduced steps for faster testing
    if token_steps is None:
        token_steps = [4096, 16384, 65536, 131072]
    if concurrency_steps is None:
        concurrency_steps = [1, 5, 10, 20]

    logger = KeyLogger(logs_dir, "test")

    # Use KeyStore for encrypted storage
    cfg = config or load_config()
    store = KeyStore(keys_file, cfg)
    data = store.load()

    keys_to_test = []
    for key, info in data["keys"].items():
        if single_key and key != single_key:
            continue
        if provider_filter and info["provider"].lower() != provider_filter.lower():
            continue
        if info["status"] != "valid":
            continue
        keys_to_test.append((key, info))

    total = len(keys_to_test)
    results = {
        "run_at": datetime.now(timezone.utc).isoformat() + "Z",
        "total_tested": total,
        "results": []
    }

    # Initialize progress
    if progress_callback:
        progress_callback(0, total)

    completed_count = 0

    async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
        for key, info in keys_to_test:
            provider_name = info["provider"].lower()
            provider = PROVIDERS.get(provider_name)
            if not provider:
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total)
                continue

            key_masked = info["key_masked"]
            test_result = {
                "key_masked": key_masked,
                "provider": info["provider"],
                "token_test": {"tested": False},
                "concurrency_test": {"tested": False},
                "models": []
            }

            # Get models list
            try:
                models = await provider.get_models(client, key)
                test_result["models"] = models[:20]  # Limit to 20 models
            except Exception:
                test_result["models"] = []

            if token_test:
                try:
                    token_result = await provider.test_token_limit(client, key, token_steps)
                    test_result["token_test"] = {
                        "tested": True,
                        "max_tokens": token_result.max_tokens,
                        "error": token_result.error
                    }
                except Exception as e:
                    test_result["token_test"] = {"tested": True, "error": str(e)}

            if concurrency_test:
                try:
                    conc_result = await provider.test_concurrency(client, key, concurrency_steps)
                    test_result["concurrency_test"] = {
                        "tested": True,
                        "max_concurrency": conc_result.max_concurrency,
                        "rpm_limit": conc_result.rpm_limit,
                        "error": conc_result.error
                    }
                except Exception as e:
                    test_result["concurrency_test"] = {"tested": True, "error": str(e)}

            results["results"].append(test_result)
            completed_count += 1

            if progress_callback:
                progress_callback(completed_count, total)

            # Update keys.json
            data["keys"][key]["tests"] = {
                "max_tokens": test_result["token_test"].get("max_tokens"),
                "max_concurrency": test_result["concurrency_test"].get("max_concurrency"),
                "rpm_limit": test_result["concurrency_test"].get("rpm_limit"),
                "models": test_result["models"],
                "tested_at": datetime.now(timezone.utc).isoformat() + "Z"
            }
            data["keys"][key]["last_tested"] = datetime.now(timezone.utc).isoformat() + "Z"

            # Log
            token_info = f"TOKEN={test_result['token_test'].get('max_tokens', 'N/A')}"
            conc_info = f"CONCURRENCY={test_result['concurrency_test'].get('max_concurrency', 'N/A')}"
            model_info = f"MODELS={len(test_result['models'])}"
            logger.log("TEST", info["provider"], key_masked, "OK", f"{token_info}, {conc_info}, {model_info}")

    # Save using KeyStore for encrypted storage
    store.save(data)

    # Results file is not sensitive, write directly
    with open(results_file, "w", encoding="utf-8") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.flush()
    return results
