import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.url_override import custom_base_url

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.config import load_config
from src.parser import import_keys
from src.validator import validate_keys
from src.checker import run_check
from src.tester import run_test
from src.proxy import get_proxy
from src.providers import PROVIDERS, get_display_name
from src.logger import project_logger

app = FastAPI(title="API Key Manager")
config = load_config()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        {"error": f"服务器内部错误: {str(exc)}"},
        status_code=500,
    )


# Global progress tracking
progress_data = {"active": False, "current": 0, "total": 0, "status": "", "results": None}


@app.get("/", response_class=HTMLResponse)
async def index():
    return get_html()


@app.get("/api/keys")
async def get_keys(provider: str = None, status: str = None, page: int = 1, page_size: int = 50):
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        return {"keys": [], "total": 0, "page": 1, "total_pages": 0}

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_keys = []
    for key, info in data["keys"].items():
        if provider and info["provider"].lower() != provider.lower():
            continue
        if status and info["status"] != status:
            continue
        tests = info.get("tests", {})
        checks = info.get("checks", [])
        last_error = None

        if checks:
            last_check = checks[-1]
            if last_check.get("status") != "valid":
                last_error = last_check.get("error")

        if info["status"] != "valid" and info["status"] != "unknown" and not last_error:
            if info["status"] == "invalid":
                last_error = "invalid key"
            elif info["status"] == "error":
                last_error = "检测失败或连接超时"

        all_keys.append({
            "key": key,
            "key_masked": info["key_masked"],
            "provider": info["provider"],
            "status": info["status"],
            "last_checked": info.get("last_checked"),
            "last_error": last_error,
            "error_type": last_check.get("error_type") if checks else None,
            "tests": tests,
            "models": tests.get("models", []),
            "sources_count": len(info.get("sources", [])),
            "balance": last_check.get("balance") if checks else None,
        })

    total = len(all_keys)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    page_keys = all_keys[start:start + page_size]

    return {"keys": page_keys, "total": total, "page": page, "total_pages": total_pages, "page_size": page_size}


@app.get("/api/keys/export")
async def export_valid_keys(provider: str = None):
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        return {"keys": [], "total": 0}

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_keys = []
    for key, info in data["keys"].items():
        if info.get("status") != "valid":
            continue
        if provider and info["provider"].lower() != provider.lower():
            continue
        valid_keys.append({
            "key": key,
            "provider": info["provider"],
            "max_tokens": info.get("tests", {}).get("max_tokens"),
            "max_concurrency": info.get("tests", {}).get("max_concurrency")
        })

    return {"keys": valid_keys, "total": len(valid_keys)}


@app.post("/api/keys/clear")
async def clear_keys():
    """Clear all imported keys."""
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        return {"cleared": 0}

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = len(data["keys"])

    data["keys"] = {}
    with open(keys_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    project_logger.log_web_action("clear_keys", f"cleared {count} keys")
    return {"cleared": count}


@app.get("/api/stats")
async def get_stats():
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        return {"providers": {}, "total": 0}

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    from src.providers import get_display_name

    stats = {}
    for key, info in data["keys"].items():
        provider = info["provider"]
        if provider not in stats:
            stats[provider] = {"total": 0, "valid": 0, "invalid": 0, "error": 0, "display_name": get_display_name(provider)}
        stats[provider]["total"] += 1
        status = info.get("status", "unknown")
        if status in stats[provider]:
            stats[provider][status] += 1

    return {"providers": stats, "total": len(data["keys"])}


@app.post("/api/import")
async def import_keys_api(request: Request):
    body = await request.json()
    file_path = body.get("file")
    directory = body.get("directory")
    batch = body.get("batch")

    new, dupes, errors = import_keys(
        file_path=file_path,
        directory=directory or config["scan"]["directories"][0],
        batch=batch,
        keys_file=config["storage"]["keys_file"]
    )

    project_logger.log_import(file_path or directory, new, dupes, errors)
    return {"new": new, "duplicates": dupes, "errors": errors}


@app.post("/api/import/upload")
async def upload_json(request: Request):
    """Upload a JSON file to import keys."""
    try:
        from starlette.requests import FormData
        import shutil

        form = await request.form()
        file = form.get("file")

        if not file:
            return JSONResponse({"error": "未选择文件"}, status_code=400)

        # Validate file type
        if not file.filename.endswith('.json'):
            return JSONResponse({"error": "只支持 .json 格式文件"}, status_code=400)

        # Save uploaded file to temp location
        temp_dir = Path("./data/input")
        temp_dir.mkdir(parents=True, exist_ok=True)

        file_path = temp_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Import keys from the uploaded file
        new, dupes, errors = import_keys(
            file_path=str(file_path),
            keys_file=config["storage"]["keys_file"]
        )

        project_logger.log_import(file.filename, new, dupes, errors)
        return {"new": new, "duplicates": dupes, "errors": errors, "filename": file.filename}

    except Exception as e:
        return JSONResponse({"error": f"上传失败: {str(e)}"}, status_code=500)


@app.post("/api/check/single")
async def check_single_key(request: Request):
    """Real usage test - actually try to use the key with a minimal request."""
    body = await request.json()
    key = body.get("key", "").strip()
    provider = body.get("provider", "").strip()
    custom_url = (body.get("custom_base_url") or "").strip() or None

    if not key:
        return JSONResponse({"error": "未提供Key"}, status_code=400)

    # Auto-detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as detect_client:
            provider = await detect_provider(detect_client, key)
        # No fallback - report actual detection result

    # Get provider instance
    from src.providers import PROVIDERS
    provider_instance = PROVIDERS.get(provider.lower())

    if not provider_instance:
        return {
            "key_masked": f"{key[:6]}...{key[-4:]}",
            "provider": provider or "unknown",
            "status": "unknown",
            "status_code": None,
            "latency_ms": 0,
            "error": f"无法识别服务商，请从下拉菜单手动选择" if provider in ("unknown", "", None) else f"服务商 '{provider}' 不支持验证"
        }

    # Check the key
    import httpx
    proxy = get_proxy(config.get("proxy", ""))
    # Set custom base URL override if provided
    token = custom_base_url.set(custom_url) if custom_url else None
    try:
        async with httpx.AsyncClient(timeout=30, proxy=proxy or None) as client:
            result = await provider_instance.check(client, key)
    except Exception as e:
        key_masked = f"{key[:6]}...{key[-4:]}"
        project_logger.log_manual_check(key_masked, provider, "error", "check", str(e))
        return {
            "key": key, "key_masked": key_masked, "provider": provider,
            "status": "error", "error": f"检测异常: {str(e)}"
        }
    finally:
        if token:
            custom_base_url.reset(token)

    # Models and balance are fetched on-demand via separate endpoints, not during check
    models = []
    balance = None

    key_masked = f"{key[:6]}...{key[-4:]}"
    # Determine error_type
    error_type = None
    if not result.valid:
        error_msg = (result.error or "").lower()
        if result.status_code in (401, 403):
            error_type = "invalid_key"
        elif result.status_code == 429:
            error_type = "rate_limited"
        elif result.status_code == 402:
            error_type = "insufficient_balance"
        elif result.status_code and result.status_code >= 500:
            error_type = "server_error"
        elif any(kw in error_msg for kw in ["balance", "quota", "欠费", "额度", "insufficient", "overdue", "payment", "standing", "arrears"]):
            error_type = "insufficient_balance"
        elif any(kw in error_msg for kw in ["rate", "limit", "限流", "too many", "throttl"]):
            error_type = "rate_limited"
        elif any(kw in error_msg for kw in ["invalid", "unauthorized", "auth", "forbidden", "denied", "key", "token"]):
            error_type = "invalid_key"
        else:
            error_type = "unknown"

    key_masked = f"{key[:6]}...{key[-4:]}"
    status = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")
    project_logger.log_manual_check(key_masked, provider, status, "check", result.error)

    return {
        "key": key,
        "key_masked": key_masked,
        "provider": provider,
        "display_name": get_display_name(provider),
        "status": status,
        "status_code": result.status_code,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "error_type": error_type,
        "balance": balance,
        "models": models,
    }



@app.post("/api/balance")
async def check_balance(request: Request):
    """Query balance for a single key."""
    body = await request.json()
    key = body.get("key", "").strip()
    provider = body.get("provider", "").strip()
    custom_url = (body.get("custom_base_url") or "").strip() or None

    if not key:
        return JSONResponse({"error": "未提供Key"}, status_code=400)

    # Auto-detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as detect_client:
            provider = await detect_provider(detect_client, key)
        if provider == 'unknown':
            return {"error": "无法识别服务商，请手动选择"}

    provider_instance = PROVIDERS.get(provider.lower())
    if not provider_instance:
        return {"error": f"服务商 '{provider}' 不支持"}

    # Check if provider supports balance
    if not hasattr(provider_instance, 'get_balance'):
        return {"provider": provider, "supported": False, "error": "该服务商不支持余额查询"}

    proxy = get_proxy(config.get("proxy", ""))
    token = custom_base_url.set(custom_url) if custom_url else None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, proxy=proxy or None) as client:
            result = await provider_instance.get_balance(client, key)
    except Exception as e:
        return {"provider": provider, "supported": False, "error": str(e)}
    finally:
        if token:
            custom_base_url.reset(token)

    if not result.supported:
        return {"provider": provider, "supported": False, "error": result.error or "该服务商不支持余额查询"}

    if result.error:
        return {"provider": provider, "supported": True, "error": result.error}

    return {
        "provider": provider,
        "supported": True,
        "balance": result.balance,
        "currency": result.currency,
        "key_masked": f"{key[:6]}...{key[-4:]}"
    }


@app.post("/api/check/batch")
async def check_batch_keys(request: Request):
    """Batch check arbitrary keys without persisting to keys.json."""
    body = await request.json()
    keys_input = body.get("keys", [])
    timeout = body.get("timeout", 10)
    concurrency = body.get("concurrency", 50)
    custom_url = (body.get("custom_base_url") or "").strip() or None

    if not keys_input:
        return JSONResponse({"error": "No keys provided"}, status_code=400)

    semaphore = asyncio.Semaphore(concurrency)
    url_token = custom_base_url.set(custom_url) if custom_url else None

    async def _check_one(item: dict) -> dict:
        key = item.get("key", "").strip()
        provider = item.get("provider", "").strip()

        if not key:
            return {
                "key_masked": "N/A",
                "provider": "unknown",
                "status": "error",
                "status_code": None,
                "latency_ms": 0,
                "error": "empty key",
                "error_type": "validation",
                "balance": None
            }

        key_masked = f"{key[:6]}...{key[-4:]}"

        # Auto-detect provider if not specified
        if not provider:
            from src.detector import detect_provider
            import httpx as _httpx
            async with _httpx.AsyncClient(timeout=5) as detect_client:
                provider = await detect_provider(detect_client, key)
            # No fallback - report actual detection result

        provider_instance = PROVIDERS.get(provider.lower())

        if not provider_instance:
            return {
                "key_masked": key_masked,
                "provider": provider,
                "status": "unknown",
                "status_code": None,
                "latency_ms": 0,
                "error": f"Provider '{provider}' not supported",
                "error_type": "provider",
                "balance": None
            }

        async with semaphore:
            import httpx
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    result = await provider_instance.check(client, key)

                latency_ms = int((time.time() - start) * 1000)
                status = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")
                error_type = None
                if not result.valid:
                    error_msg = (result.error or "").lower()
                    if result.status_code in (401, 403):
                        error_type = "invalid_key"
                    elif result.status_code == 429:
                        error_type = "rate_limited"
                    elif result.status_code == 402:
                        error_type = "insufficient_balance"
                    elif result.status_code and result.status_code >= 500:
                        error_type = "server_error"
                    elif any(kw in error_msg for kw in ["balance", "quota", "欠费", "额度", "insufficient", "overdue", "payment", "standing", "arrears"]):
                        error_type = "insufficient_balance"
                    elif any(kw in error_msg for kw in ["rate", "limit", "限流", "too many", "throttl"]):
                        error_type = "rate_limited"
                    elif any(kw in error_msg for kw in ["invalid", "unauthorized", "auth", "forbidden", "denied", "key", "token"]):
                        error_type = "invalid_key"
                    else:
                        error_type = "unknown"

                # Balance is fetched on-demand via separate endpoint
                balance = None

                return {
                    "key_masked": key_masked,
                    "provider": provider,
                    "status": status,
                    "status_code": result.status_code,
                    "latency_ms": latency_ms,
                    "error": result.error,
                    "error_type": error_type,
                    "balance": {"amount": balance.balance, "currency": balance.currency} if balance and balance.supported and balance.balance is not None else None
                }
            except Exception as e:
                latency_ms = int((time.time() - start) * 1000)
                return {
                    "key_masked": key_masked,
                    "provider": provider,
                    "status": "error",
                    "status_code": None,
                    "latency_ms": latency_ms,
                    "error": str(e),
                    "error_type": "exception",
                    "balance": None
                }

    try:
        tasks = [_check_one(item) for item in keys_input]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any unexpected exceptions
        safe_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                safe_results.append({
                    "key_masked": keys_input[i].get("key", "")[:6] + "...",
                    "provider": keys_input[i].get("provider", "unknown"),
                    "status": "error",
                    "status_code": None,
                    "latency_ms": 0,
                    "error": str(r),
                    "error_type": "exception",
                    "balance": None
                })
            else:
                safe_results.append(r)

        valid_count = sum(1 for r in safe_results if r["status"] == "valid")
        invalid_count = sum(1 for r in safe_results if r["status"] == "invalid")
        error_count = sum(1 for r in safe_results if r["status"] in ("error", "unknown"))

        project_logger.log_web_action("batch_check", f"total={len(keys_input)} valid={valid_count} invalid={invalid_count} error={error_count}")

        return {
            "results": safe_results,
            "summary": {
                "total": len(safe_results),
                "valid": valid_count,
                "invalid": invalid_count,
                "error": error_count
            }
        }
    finally:
        if url_token:
            custom_base_url.reset(url_token)
@app.post("/api/check")
async def check_keys_api(request: Request):
    global progress_data
    body = await request.json()
    provider = body.get("provider")
    single_key = body.get("key")
    proxy = get_proxy(config.get("proxy", ""))

    progress_data = {"active": True, "current": 0, "total": 0, "status": "loading", "results": None}

    def update_progress(current, total):
        global progress_data
        progress_data = {"active": True, "current": current, "total": total, "status": "loading", "results": None}

    try:
        results = await validate_keys(
            keys_file=config["storage"]["keys_file"],
            results_file=config["storage"]["check_results_file"],
            logs_dir=config["storage"]["logs_dir"],
            concurrency=config["check"]["concurrency"],
            timeout=10,
            proxy=proxy or None,
            provider_filter=provider,
            single_key=single_key,
            progress_callback=update_progress
        )
        progress_data = {"active": False, "current": results["total"], "total": results["total"], "status": "done", "results": results}
        return results
    except Exception as e:
        progress_data = {"active": False, "current": 0, "total": 0, "status": "error", "results": {"error": str(e)}}
        raise


@app.post("/api/test")
async def test_keys_api(request: Request):
    global progress_data
    body = await request.json()
    provider = body.get("provider")
    single_key = body.get("key")
    skip_token = body.get("skip_token", False)
    skip_concurrency = body.get("skip_concurrency", False)
    proxy = get_proxy(config.get("proxy", ""))

    progress_data = {"active": True, "current": 0, "total": 0, "status": "loading", "results": None}

    def update_progress(current, total):
        global progress_data
        progress_data = {"active": True, "current": current, "total": total, "status": "loading", "results": None}

    try:
        results = await run_test(
            keys_file=config["storage"]["keys_file"],
            results_file=config["storage"]["test_results_file"],
            logs_dir=config["storage"]["logs_dir"],
            timeout=15,  # Reduced timeout
            proxy=proxy or None,
            token_test=not skip_token,
            concurrency_test=not skip_concurrency,
            token_steps=[4096, 16384, 65536, 131072],  # Reduced steps
            concurrency_steps=[1, 5, 10, 20],  # Reduced steps
            provider_filter=provider,
            single_key=single_key,
            progress_callback=update_progress
        )
        progress_data = {"active": False, "current": results["total_tested"], "total": results["total_tested"], "status": "done", "results": results}
        return results
    except Exception as e:
        progress_data = {"active": False, "current": 0, "total": 0, "status": "error", "results": {"error": str(e)}}
        raise


@app.post("/api/test/single")
async def test_single_key(request: Request):
    """Test a single key's concurrency and token limits."""
    body = await request.json()
    key = body.get("key", "").strip()
    provider = body.get("provider", "").strip()

    if not key:
        return JSONResponse({"error": "未提供Key"}, status_code=400)

    # Auto-detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as detect_client:
            provider = await detect_provider(detect_client, key)
        if provider == 'unknown':
            return {"error": "无法识别服务商，请手动选择"}

    from src.providers import PROVIDERS
    provider_instance = PROVIDERS.get(provider.lower())
    if not provider_instance:
        return {"error": f"服务商 '{provider}' 不支持"}

    # Run test
    import httpx
    proxy = get_proxy(config.get("proxy", ""))
    try:
        async with httpx.AsyncClient(timeout=30, proxy=proxy or None) as client:
            # Test token limit
            token_result = await provider_instance.test_token_limit(
                client, key, config["test"]["token_steps"]
            )
            # Test concurrency
            concurrency_result = await provider_instance.test_concurrency(
                client, key, config["test"]["concurrency_steps"]
            )

        return {
            "provider": provider,
            "key_masked": f"{key[:6]}...{key[-4:]}",
            "max_tokens": token_result.max_tokens,
            "max_concurrency": concurrency_result.max_concurrency,
            "models": token_result.models or []
        }
    except Exception as e:
        return {"error": str(e), "provider": provider}


@app.post("/api/test/concurrency")
async def test_concurrency_endpoint(request: Request):
    """Test concurrency limit for each available model."""
    body = await request.json()
    key = body.get("key", "").strip()
    provider = body.get("provider", "").strip()
    concurrency = body.get("concurrency", 10)

    if not key:
        return JSONResponse({"error": "未提供Key"}, status_code=400)

    # Auto-detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as detect_client:
            provider = await detect_provider(detect_client, key)
        if provider == 'unknown':
            return {"error": "无法识别服务商，请手动选择"}

    from src.providers import PROVIDERS
    provider_instance = PROVIDERS.get(provider.lower())
    if not provider_instance:
        return {"error": f"服务商 '{provider}' 不支持"}

    # Get available models
    import httpx
    proxy = get_proxy(config.get("proxy", ""))
    try:
        async with httpx.AsyncClient(timeout=10, proxy=proxy or None) as client:
            models = await provider_instance.get_models(client, key)
    except Exception as e:
        return {"error": f"获取模型失败: {str(e)}"}

    if not models:
        return {"error": "未找到可用模型", "provider": provider}

    # Test concurrency per model (limit to first 5 models)
    results = []
    for model in models[:5]:
        try:
            async with httpx.AsyncClient(timeout=60, proxy=proxy or None) as client:
                result = await provider_instance.test_concurrency_for_model(
                    client, key, model, [concurrency]
                )
                results.append({"model": model, "max_concurrency": result.max_concurrency})
        except Exception:
            results.append({"model": model, "max_concurrency": None})

    return {
        "provider": provider,
        "key_masked": f"{key[:6]}...{key[-4:]}",
        "total_models": len(models),
        "tested_models": len(results),
        "results": results
    }


@app.post("/api/test/token")
async def test_token_per_model(request: Request):
    """Test max token limit for each available model."""
    import re
    body = await request.json()
    key = body.get("key", "").strip()
    provider = body.get("provider", "").strip()

    if not key:
        return JSONResponse({"error": "未提供Key"}, status_code=400)

    # Auto-detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as detect_client:
            provider = await detect_provider(detect_client, key)
        if provider == 'unknown':
            return {"error": "无法识别服务商，请手动选择"}

    from src.providers import PROVIDERS
    provider_instance = PROVIDERS.get(provider.lower())
    if not provider_instance:
        return {"error": f"服务商 '{provider}' 不支持"}

    # Get available models
    import httpx
    proxy = get_proxy(config.get("proxy", ""))
    try:
        async with httpx.AsyncClient(timeout=10, proxy=proxy or None) as client:
            models = await provider_instance.get_models(client, key)
    except Exception as e:
        return {"error": f"获取模型失败: {str(e)}"}

    if not models:
        return {"error": "未找到可用模型", "provider": provider}

    # Use a very large token value to trigger error and find the limit
    test_token_value = 1048576  # 1M - reasonable upper bound for token limit testing

    # Test token limit for each model (limit to first 5 models)
    results = []
    for model in models[:5]:
        try:
            async with httpx.AsyncClient(timeout=30, proxy=proxy or None) as client:
                headers = provider_instance.build_headers(key)
                headers["Content-Type"] = "application/json"
                resp = await client.post(
                    f"{provider_instance.get_base_url()}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": test_token_value
                    }
                )
                if resp.status_code == 200:
                    # Somehow accepted the huge value (unlikely)
                    results.append({
                        "model": model,
                        "max_tokens": test_token_value,
                        "success": True,
                        "error": None
                    })
                else:
                    error_msg = ""
                    try:
                        data = resp.json()
                        error_msg = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                    except:
                        error_msg = f"HTTP {resp.status_code}"
                    
                    # Parse the max allowed token from error message
                    max_tokens = None
                    range_match = re.search(r'\[(\d+),\s*(\d+)\]', error_msg)
                    if range_match:
                        max_tokens = int(range_match.group(2))
                    
                    results.append({
                        "model": model,
                        "max_tokens": max_tokens,
                        "success": False,
                        "error": error_msg
                    })
        except Exception as e:
            results.append({
                "model": model,
                "max_tokens": None,
                "success": False,
                "error": str(e)
            })
    return {
        "provider": provider,
        "key_masked": f"{key[:6]}...{key[-4:]}",
        "total_models": len(models),
        "tested_models": len(results),
        "results": results
    }


@app.post("/api/test/token/batch")
async def test_token_batch(request: Request):
    """Batch test token limits for all valid keys using error-parsing method."""
    import re
    global progress_data
    body = await request.json()
    provider_filter = body.get("provider")

    with open(config["storage"]["keys_file"], "r", encoding="utf-8") as f:
        data = json.load(f)

    keys_to_test = [(k, i) for k, i in data["keys"].items() if i["status"] == "valid"]
    if provider_filter:
        keys_to_test = [(k, i) for k, i in keys_to_test if i["provider"].lower() == provider_filter.lower()]

    total = len(keys_to_test)
    if total == 0:
        return {"total_tested": 0, "results": []}

    progress_data = {"active": True, "current": 0, "total": total, "status": "loading", "results": None}
    proxy = get_proxy(config.get("proxy", ""))
    test_token_value = 1048576
    completed = 0
    results = []

    async with httpx.AsyncClient(timeout=30, proxy=proxy or None) as client:
        for key, info in keys_to_test:
            provider_name = info["provider"].lower()
            provider_instance = PROVIDERS.get(provider_name)
            if not provider_instance:
                completed += 1
                progress_data = {"active": True, "current": completed, "total": total, "status": "loading", "results": None}
                continue

            try:
                models = await provider_instance.get_models(client, key)
            except Exception:
                models = []

            token_results = []
            if models:
                for model in models[:5]:
                    try:
                        headers = provider_instance.build_headers(key)
                        headers["Content-Type"] = "application/json"
                        resp = await client.post(
                            f"{provider_instance.get_base_url()}/chat/completions",
                            headers=headers,
                            json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": test_token_value}
                        )
                        if resp.status_code == 200:
                            token_results.append({"model": model, "max_tokens": test_token_value})
                        else:
                            error_msg = ""
                            try:
                                rdata = resp.json()
                                error_msg = rdata.get("error", {}).get("message", f"HTTP {resp.status_code}")
                            except:
                                error_msg = f"HTTP {resp.status_code}"
                            max_tokens = None
                            range_match = re.search(r'\[(\d+),\s*(\d+)\]', error_msg)
                            if range_match:
                                max_tokens = int(range_match.group(2))
                            token_results.append({"model": model, "max_tokens": max_tokens})
                    except Exception:
                        token_results.append({"model": model, "max_tokens": None})

            # Pick the best max_tokens from results
            all_max = [r["max_tokens"] for r in token_results if r.get("max_tokens")]
            best_max = min(all_max) if all_max else None

            # Update keys.json
            if "tests" not in data["keys"][key]:
                data["keys"][key]["tests"] = {}
            data["keys"][key]["tests"]["max_tokens"] = best_max
            data["keys"][key]["tests"]["models"] = [r["model"] for r in token_results]
            data["keys"][key]["tests"]["tested_at"] = datetime.utcnow().isoformat() + "Z"
            data["keys"][key]["last_tested"] = datetime.utcnow().isoformat() + "Z"

            results.append({
                "key_masked": info["key_masked"],
                "provider": provider_name,
                "max_tokens": best_max,
                "model_results": token_results
            })

            completed += 1
            progress_data = {"active": True, "current": completed, "total": total, "status": "loading", "results": None}

    # Save
    with open(config["storage"]["keys_file"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    progress_data = {"active": False, "current": total, "total": total, "status": "done", "results": None}
    return {"total_tested": total, "results": results}


@app.post("/api/test/concurrency/batch")
async def test_concurrency_batch(request: Request):
    """Batch test concurrency for all valid keys using per-model method."""
    global progress_data
    body = await request.json()
    provider_filter = body.get("provider")
    concurrency = body.get("concurrency", 10)

    with open(config["storage"]["keys_file"], "r", encoding="utf-8") as f:
        data = json.load(f)

    keys_to_test = [(k, i) for k, i in data["keys"].items() if i["status"] == "valid"]
    if provider_filter:
        keys_to_test = [(k, i) for k, i in keys_to_test if i["provider"].lower() == provider_filter.lower()]

    total = len(keys_to_test)
    if total == 0:
        return {"total_tested": 0, "results": []}

    progress_data = {"active": True, "current": 0, "total": total, "status": "loading", "results": None}
    proxy = get_proxy(config.get("proxy", ""))
    completed = 0
    results = []

    async with httpx.AsyncClient(timeout=60, proxy=proxy or None) as client:
        for key, info in keys_to_test:
            provider_name = info["provider"].lower()
            provider_instance = PROVIDERS.get(provider_name)
            if not provider_instance:
                completed += 1
                progress_data = {"active": True, "current": completed, "total": total, "status": "loading", "results": None}
                continue

            try:
                models = await provider_instance.get_models(client, key)
            except Exception:
                models = []

            conc_results = []
            best_conc = None
            if models:
                for model in models[:5]:
                    try:
                        result = await provider_instance.test_concurrency_for_model(
                            client, key, model, [concurrency]
                        )
                        conc_results.append({"model": model, "max_concurrency": result.max_concurrency})
                        if result.max_concurrency and (best_conc is None or result.max_concurrency > best_conc):
                            best_conc = result.max_concurrency
                    except Exception:
                        conc_results.append({"model": model, "max_concurrency": None})

            # Update keys.json
            if "tests" not in data["keys"][key]:
                data["keys"][key]["tests"] = {}
            data["keys"][key]["tests"]["max_concurrency"] = best_conc
            data["keys"][key]["tests"]["models"] = [r["model"] for r in conc_results]
            data["keys"][key]["tests"]["tested_at"] = datetime.utcnow().isoformat() + "Z"
            data["keys"][key]["last_tested"] = datetime.utcnow().isoformat() + "Z"

            results.append({
                "key_masked": info["key_masked"],
                "provider": provider_name,
                "max_concurrency": best_conc,
                "model_results": conc_results
            })

            completed += 1
            progress_data = {"active": True, "current": completed, "total": total, "status": "loading", "results": None}

    # Save
    with open(config["storage"]["keys_file"], "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    progress_data = {"active": False, "current": total, "total": total, "status": "done", "results": None}
    return {"total_tested": total, "results": results}
@app.get("/api/progress")
async def get_progress():
    return progress_data


@app.get("/api/progress/stream")
async def stream_progress():
    async def event_generator():
        last_state = None
        while True:
            current_state = json.dumps(progress_data)
            if current_state != last_state:
                yield f"data: {current_state}\n\n"
                last_state = current_state
            if not progress_data["active"]:
                yield f"data: {current_state}\n\n"
                break
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/proxy")
async def get_proxy_status():
    proxy = get_proxy(config.get("proxy", ""))
    return {"proxy": proxy or "未检测到代理"}


@app.get("/api/providers")
async def get_providers():
    from src.providers import PROVIDERS, KEY_PREFIX_MAP, get_display_name

    provider_prefix = {}
    for prefix, names in KEY_PREFIX_MAP.items():
        for name in names:
            if name not in provider_prefix:
                provider_prefix[name] = prefix

    providers = []
    for name, p in sorted(PROVIDERS.items()):
        prefix = provider_prefix.get(name, '-')
        providers.append({
            'name': name,
            'display_name': get_display_name(name),
            'prefix': prefix,
            'base_url': p.base_url if hasattr(p, 'base_url') else '',
            'type': 'ai',
        })

    return {'providers': providers, 'total': len(providers)}


@app.get("/api/models")
async def get_models(provider: str = None, key: str = None, type: str = None):
    """Get available models for a provider or key.
    
    Args:
        provider: Provider name
        key: API key for auto-detection
        type: Model type filter (vision, tooluse, embedding, rerank, all)
    """
    from src.providers import PROVIDERS
    import httpx
    from src.model_capabilities import detector

    if not provider and not key:
        return {"error": "Please provide provider or key", "models": []}

    # If key provided, detect provider first
    if key and not provider:
        from src.detector import detect_provider
        async with httpx.AsyncClient(timeout=5) as client:
            provider = await detect_provider(client, key)
        if provider == 'unknown':
            return {"error": "Cannot detect provider", "models": []}

    provider_instance = PROVIDERS.get(provider.lower()) if provider else None
    if not provider_instance:
        return {"error": f"Provider '{provider}' not found", "models": []}

    # Get models from provider
    source = "api"  # Track where models came from
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # If key provided, use key to get models
            if key:
                models = await provider_instance.get_models(client, key)
            else:
                # No key, try public API (some providers support this)
                models = await provider_instance.get_models(client, '')
                
                # If public API failed, use static registry
                if not models:
                    from src.providers.models_registry import get_static_models
                    models = get_static_models(provider.lower())
                    source = "static"
                    
                    if not models:
                        return {
                            "provider": provider,
                            "models": [],
                            "total": 0,
                            "type_filter": type or 'all',
                            "hint": "API key required to fetch models"
                        }
    except Exception as e:
        # On error, fallback to static registry
        from src.providers.models_registry import get_static_models
        models = get_static_models(provider.lower())
        source = "static"
        
        if not models:
            return {"error": str(e), "provider": provider, "models": []}

    # Filter by type if specified
    if type and type != 'all':
        # Ensure detector is loaded
        if not detector.is_loaded:
            await detector.load()
        
        filtered_models = []
        for model_id in models:
            if type == 'vision' and detector.is_vision_model(model_id):
                filtered_models.append(model_id)
            elif type == 'tooluse' and detector.is_tool_model(model_id):
                filtered_models.append(model_id)
            elif type == 'embedding' and detector.is_embedding_model(model_id):
                filtered_models.append(model_id)
            elif type == 'rerank' and detector.is_rerank_model(model_id):
                filtered_models.append(model_id)
            elif type == 'reasoning' and detector.is_reasoning_model(model_id):
                filtered_models.append(model_id)
            elif type == 'websearch' and detector.is_websearch_model(model_id):
                filtered_models.append(model_id)
            elif type == 'free' and detector.is_free_model(model_id):
                filtered_models.append(model_id)
        models = filtered_models

    return {"provider": provider, "models": models, "total": len(models), "type_filter": type or 'all', "source": source}

@app.post("/api/models/check")
async def check_available_models(request: Request):
    """Check which models are actually available by sending test requests.
    
    Returns SSE stream with progress updates.
    """
    body = await request.json()
    key = body.get('key', '').strip()
    provider = body.get('provider', '').strip()
    model_type = body.get('type', '').strip()  # 新增：模型类型筛选
    
    if not key:
        return JSONResponse({"error": "Key is required"}, status_code=400)
    
    # Detect provider if not specified
    if not provider:
        from src.detector import detect_provider
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            provider = await detect_provider(client, key)
        if provider == 'unknown':
            return JSONResponse({"error": "Cannot detect provider"}, status_code=400)
    
    # Get provider instance
    provider_instance = PROVIDERS.get(provider.lower())
    if not provider_instance:
        return JSONResponse({"error": f"Provider '{provider}' not found"}, status_code=400)
    
    # Get models list first
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            models = await provider_instance.get_models(client, key)
    except Exception as e:
        return JSONResponse({"error": f"Failed to get models: {str(e)}"}, status_code=500)
    
    if not models:
        return JSONResponse({"error": "No models found"}, status_code=404)
    
    # Apply type filter if specified
    if model_type and model_type != 'all':
        from src.model_capabilities import detector
        if not detector.is_loaded:
            await detector.load()
        
        filtered_models = []
        for model_id in models:
            if model_type == 'vision' and detector.is_vision_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'tooluse' and detector.is_tool_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'embedding' and detector.is_embedding_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'rerank' and detector.is_rerank_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'reasoning' and detector.is_reasoning_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'websearch' and detector.is_websearch_model(model_id):
                filtered_models.append(model_id)
            elif model_type == 'free' and detector.is_free_model(model_id):
                filtered_models.append(model_id)
        models = filtered_models
        
        if not models:
            return JSONResponse({"error": f"No models found for type '{model_type}'"}, status_code=404)
    
    async def generate():
        """Generate SSE stream for model checking progress"""
        total = len(models)
        available_count = 0
        timeout_count = 0
        rate_limited = False
        concurrency = 5  # Initial concurrency
        single_timeout = 15  # 15 seconds per model
        
        # Send initial progress
        yield f"data: {{\"type\": \"progress\", \"current\": 0, \"total\": {total}, \"model\": \"starting\", \"concurrency\": {concurrency}}}\n\n"
        
        async def check_model(client, model_id, index):
            """Check single model availability with timeout"""
            nonlocal available_count, timeout_count, rate_limited
            
            # If rate limited, use serial mode with delay
            if rate_limited:
                await asyncio.sleep(1)  # Delay between requests
            
            try:
                headers = provider_instance.build_headers(key)
                headers["Content-Type"] = "application/json"
                
                # Use asyncio.wait_for for timeout
                async def do_request():
                    return await client.post(
                        f"{provider_instance.get_base_url()}/chat/completions",
                        headers=headers,
                        json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                    )
                
                resp = await asyncio.wait_for(do_request(), timeout=single_timeout)
                
                if resp.status_code == 429:
                    # Rate limited - switch to serial mode
                    rate_limited = True
                    return model_id, False, "rate_limited"
                
                available = resp.status_code == 200
                if available:
                    available_count += 1
                    return model_id, True, "ok"
                else:
                    return model_id, False, "error"
            except asyncio.TimeoutError:
                timeout_count += 1
                return model_id, False, "timeout"
            except Exception:
                return model_id, False, "error"
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=30.0, connect=10.0)) as client:
            if rate_limited:
                # Serial mode (after rate limit)
                for i, model_id in enumerate(models):
                    yield f"data: {{\"type\": \"progress\", \"current\": {i+1}, \"total\": {total}, \"model\": \"{model_id}\", \"mode\": \"serial\"}}\n\n"
                    _, available, status = await check_model(client, model_id, i)
                    if status == "rate_limited":
                        yield f"data: {{\"type\": \"rate_limited\", \"model\": \"{model_id}\"}}\n\n"
                    elif status == "timeout":
                        yield f"data: {{\"type\": \"model_timeout\", \"model\": \"{model_id}\"}}\n\n"
                    yield f"data: {{\"type\": \"result\", \"model\": \"{model_id}\", \"available\": {str(available).lower()}, \"status\": \"{status}\"}}\n\n"
            else:
                # Parallel mode (initial)
                semaphore = asyncio.Semaphore(concurrency)
                completed = 0
                
                async def bounded_check(model_id, index):
                    async with semaphore:
                        return await check_model(client, model_id, index)
                
                # Run all checks in parallel
                tasks = [bounded_check(m, i) for i, m in enumerate(models)]
                for coro in asyncio.as_completed(tasks):
                    model_id, available, status = await coro
                    completed += 1
                    yield f"data: {{\"type\": \"progress\", \"current\": {completed}, \"total\": {total}, \"model\": \"{model_id}\", \"mode\": \"parallel\"}}\n\n"
                    if status == "rate_limited":
                        yield f"data: {{\"type\": \"rate_limited\", \"model\": \"{model_id}\"}}\n\n"
                    elif status == "timeout":
                        yield f"data: {{\"type\": \"model_timeout\", \"model\": \"{model_id}\"}}\n\n"
                    yield f"data: {{\"type\": \"result\", \"model\": \"{model_id}\", \"available\": {str(available).lower()}, \"status\": \"{status}\"}}\n\n"
        
        # Send completion
        mode = "serial" if rate_limited else "parallel"
        yield f"data: {{\"type\": \"complete\", \"total\": {total}, \"available\": {available_count}, \"timeout\": {timeout_count}, \"mode\": \"{mode}\"}}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """Get recent log entries."""
    logs = project_logger.get_recent_logs(lines)
    return {"logs": logs, "total": len(logs)}


@app.get("/api/logs/operations")
async def get_operations(limit: int = 50):
    """Get structured operations log."""
    ops = project_logger.get_operations_log(limit)
    return {"operations": ops, "total": len(ops)}


@app.get("/api/logs/files")
async def get_log_files():
    """Get list of log files."""
    files = project_logger.get_log_files()
    return {"files": files}


@app.get("/api/stats/chart")
async def get_stats_chart():
    """Get stats for chart visualization."""
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        return {"providers": {}, "statuses": {}, "timeline": []}

    with open(keys_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    providers = {}
    statuses = {"valid": 0, "invalid": 0, "error": 0, "unknown": 0}

    for key, info in data["keys"].items():
        provider = info["provider"]
        status = info.get("status", "unknown")

        if provider not in providers:
            providers[provider] = {"total": 0, "valid": 0, "invalid": 0, "error": 0}
        providers[provider]["total"] += 1
        if status in providers[provider]:
            providers[provider][status] += 1
        if status in statuses:
            statuses[status] += 1

    return {"providers": providers, "statuses": statuses}



@app.get("/api/providers/detail")
async def get_provider_detail(provider: str = None):
    """Get provider detail including website and docs links."""
    from src.providers import PROVIDERS, KEY_PREFIX_MAP, get_display_name, PROVIDER_WEBSITES

    if provider:
        # Return detail for a specific provider
        p = PROVIDERS.get(provider.lower())
        if not p:
            return JSONResponse({"error": f"Provider '{provider}' not found"}, status_code=404)
        prefix = None
        for k, names in KEY_PREFIX_MAP.items():
            if provider.lower() in names:
                prefix = k
                break
        website = PROVIDER_WEBSITES.get(provider.lower(), {})
        return {
            "name": provider.lower(),
            "display_name": get_display_name(provider.lower()),
            "prefix": prefix or '-',
            "base_url": p.base_url if hasattr(p, 'base_url') else '',
            "website_url": website.get('url', ''),
            "docs_url": website.get('docs', ''),
            "website_name": website.get('name', ''),
        }
    else:
        # Return all providers with website info
        providers = []
        for name, p in sorted(PROVIDERS.items()):
            prefix = None
            for k, names in KEY_PREFIX_MAP.items():
                if name in names:
                    prefix = k
                    break
            website = PROVIDER_WEBSITES.get(name, {})
            providers.append({
                'name': name,
                'display_name': get_display_name(name),
                'prefix': prefix or '-',
                'base_url': p.base_url if hasattr(p, 'base_url') else '',
                'website_url': website.get('url', ''),
                'docs_url': website.get('docs', ''),
                'website_name': website.get('name', ''),
            })
        return {'providers': providers, 'total': len(providers)}


@app.get("/api/signature-report")
async def get_signature_report():
    """Return the signature verification report."""
    report_path = Path("data/signature_verification_report.json")
    if not report_path.exists():
        return JSONResponse({"error": "签名验证报告不存在，请先运行 verify_signatures.py"}, status_code=404)
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        return report
    except Exception as e:
        return JSONResponse({"error": f"读取报告失败: {str(e)}"}, status_code=500)

def get_html():
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Error: templates/index.html not found</h1>"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18001)
