

from .validator import validate_keys


async def run_check(keys_file: str = "./data/keys.json",
                    results_file: str = "./data/check_results.json",
                    logs_dir: str = "./data/logs",
                    concurrency: int = 100,
                    timeout: int = 30,
                    proxy: str = None,
                    retry_failed: bool = True,
                    retry_count: int = 2,
                    config: dict = None) -> dict:
    results = await validate_keys(
        keys_file=keys_file,
        results_file=results_file,
        logs_dir=logs_dir,
        concurrency=concurrency,
        timeout=timeout,
        proxy=proxy,
        config=config
    )

    # Retry failed keys
    if retry_failed and results["summary"]["error"]["count"] > 0:
        for _i in range(retry_count):
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
                status_filter="error",
                config=config
            )

            # Recompute summary from details to avoid double-counting
            # The retry only re-checks error keys, so we need to update the summary
            # based on what changed
            results["summary"]["error"]["count"] = retry_results["summary"]["error"]["count"]
            results["summary"]["error"]["keys"] = retry_results["summary"]["error"]["keys"]
            results["summary"]["valid"]["count"] += retry_results["summary"]["valid"]["count"]
            results["summary"]["valid"]["keys"].extend(retry_results["summary"]["valid"]["keys"])
            results["summary"]["invalid"]["count"] += retry_results["summary"]["invalid"]["count"]
            results["summary"]["invalid"]["keys"].extend(retry_results["summary"]["invalid"]["keys"])

    return results
