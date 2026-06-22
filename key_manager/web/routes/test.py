"""Test routes: token limit and concurrency testing."""

import asyncio

import httpx
from key_manager.web.utils import build_chat_url, resolve_provider
from fastapi import APIRouter, Request

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import TestSingleRequest, TestSingleResponse
from key_manager.errors import ErrorCode, ValidationError
from key_manager.i18n import t
from key_manager.logger import project_logger
from key_manager.parser import mask_key
from key_manager.proxy import get_proxy
from key_manager.tester import run_test
from key_manager.web.progress import _make_progress_callback, _progress_tracker
from key_manager.webhook import WebhookEvent, webhook_manager

router = APIRouter(tags=["Test"])


@router.post("/api/test")
async def api_test():
    """Run token limit and concurrency tests against all valid keys (async)."""
    proxy = get_proxy(_app_mod.config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=_app_mod.config["storage"]["keys_file"],
                results_file=_app_mod.config["storage"]["test_results_file"],
                logs_dir=_app_mod.config["storage"]["logs_dir"],
                timeout=_app_mod.config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=_app_mod.config["test"].get("token_test", True),
                concurrency_test=_app_mod.config["test"].get("concurrency_test", True),
                token_steps=_app_mod.config["test"]["token_steps"],
                concurrency_steps=_app_mod.config["test"]["concurrency_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
            project_logger.log_web_action("test_all", f"tested={results.get('total_tested', 0)}")
            await webhook_manager.dispatch(
                WebhookEvent.BATCH_TEST_COMPLETED,
                {"total_tested": results.get("total_tested", 0)},
            )
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})
            await webhook_manager.dispatch(
                WebhookEvent.ERROR_OCCURRED,
                {"error": str(e)},
            )

    _progress_tracker.start(total=0, status="loading")
    task = asyncio.create_task(_run())
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)  # Suppress unhandled exception warning
    return {"message": "Test started", "status": "loading"}


@router.post("/api/test/single", response_model=TestSingleResponse)
async def api_test_single(body: TestSingleRequest):
    """Test token limit and concurrency for a single key."""
    key = (body.key or "").strip()
    provider_name = (body.provider or "").strip()

    if not key:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    provider_name, provider_obj = await resolve_provider(
        key=key,
        provider_name=provider_name,
        timeout=_app_mod.config.get("check", {}).get("timeout_seconds", 30),
        proxy=get_proxy(_app_mod.config.get("proxy")),
        providers=_app_mod.PROVIDERS,
        detect_provider_fn=_app_mod.detect_provider,
    )

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    token_steps = _app_mod.config["test"]["token_steps"]
    concurrency_steps = _app_mod.config["test"]["concurrency_steps"]

    max_tokens = None
    max_concurrency = None
    models: list[str] = []
    error = None

    async with httpx.AsyncClient(
        timeout=_app_mod.config["test"]["concurrency_timeout_seconds"],
        proxy=proxy,
    ) as client:
        # Token test
        try:
            token_result = await provider_obj.test_token_limit(client, key, token_steps)
            max_tokens = token_result.max_tokens
            if token_result.error:
                error = token_result.error
        except Exception as e:
            if not error:
                error = str(e)

        # Concurrency test
        try:
            conc_result = await provider_obj.test_concurrency(client, key, concurrency_steps)
            max_concurrency = conc_result.max_concurrency
            if conc_result.error and not error:
                error = conc_result.error
        except Exception as e:
            if not error:
                error = str(e)

        # Models
        try:
            if hasattr(provider_obj, "get_models"):
                models = await provider_obj.get_models(client, key) or []
        except Exception:
            pass

    project_logger.log_web_action(
        "test_single",
        f"{mask_key(key)} {provider_name}: tokens={max_tokens}, concurrency={max_concurrency}",
    )

    return TestSingleResponse(
        provider=provider_name,
        key_masked=mask_key(key),
        max_tokens=max_tokens,
        max_concurrency=max_concurrency,
        models=models,
        error=error,
    )


@router.post("/api/test/token")
async def api_test_token():
    """Run token limit tests on all valid keys (async)."""
    proxy = get_proxy(_app_mod.config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=_app_mod.config["storage"]["keys_file"],
                results_file=_app_mod.config["storage"]["test_results_file"],
                logs_dir=_app_mod.config["storage"]["logs_dir"],
                timeout=_app_mod.config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=True,
                concurrency_test=False,
                token_steps=_app_mod.config["test"]["token_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})

    _progress_tracker.start(total=0, status="loading")
    task = asyncio.create_task(_run())
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)  # Suppress unhandled exception warning
    return {"message": "Token test started", "status": "loading"}


@router.post("/api/test/token/batch", include_in_schema=False)
async def api_test_token_batch():
    """Run token limit tests on specific keys (batch alias)."""
    return await api_test_token()


@router.post("/api/test/concurrency")
async def api_test_concurrency():
    """Run concurrency tests on all valid keys (async)."""
    proxy = get_proxy(_app_mod.config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=_app_mod.config["storage"]["keys_file"],
                results_file=_app_mod.config["storage"]["test_results_file"],
                logs_dir=_app_mod.config["storage"]["logs_dir"],
                timeout=_app_mod.config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=False,
                concurrency_test=True,
                concurrency_steps=_app_mod.config["test"]["concurrency_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})

    _progress_tracker.start(total=0, status="loading")
    task = asyncio.create_task(_run())
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)  # Suppress unhandled exception warning
    return {"message": "Concurrency test started", "status": "loading"}


@router.post("/api/test/concurrency/batch", include_in_schema=False)
async def api_test_concurrency_batch():
    """Run concurrency tests on specific keys (batch alias)."""
    return await api_test_concurrency()


@router.post("/api/test/concurrency/model")
async def api_test_concurrency_model(request: Request):
    """Run concurrency test for a specific model."""
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body") from e

    key = (body.get("key") or "").strip()
    provider_name = (body.get("provider") or "").lower()
    model = (body.get("model") or "").strip()
    concurrency = body.get("concurrency", 10)

    if not key:
        raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY, message="Missing key")

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    provider_name, provider_obj = await resolve_provider(
        key=key,
        provider_name=provider_name or None,
        timeout=_app_mod.config.get("check", {}).get("timeout_seconds", 30),
        proxy=proxy,
        providers=_app_mod.PROVIDERS,
        detect_provider_fn=_app_mod.detect_provider,
    )

    # If no model specified, get models and find a free one
    if not model:
        async with httpx.AsyncClient(timeout=_app_mod.config["check"]["timeout_seconds"], proxy=proxy) as client:
            models = await provider_obj.get_models(client, key) or []
            if not models:
                return {"error": "No models available"}
            # Find first free model (contains 'free' in name)
            free_models = [m for m in models if 'free' in m.lower()]
            if free_models:
                model = free_models[0]
            else:
                # Use first model
                model = models[0]

    # Run test
    try:
        async with httpx.AsyncClient(timeout=_app_mod.config["test"]["concurrency_timeout_seconds"], proxy=proxy) as client:
            headers = provider_obj.build_headers(key)
            headers["Content-Type"] = "application/json"

            chat_url = build_chat_url(provider_obj)

            # Test concurrency
            async def probe_model(m):
                try:
                    resp = await client.post(
                        chat_url,
                        headers=headers,
                        json={"model": m, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                    )
                    if resp.status_code == 200:
                        return {"success": True}
                    else:
                        try:
                            error_data = resp.json()
                            if 'error' in error_data:
                                error_msg = error_data['error'].get('message', str(error_data['error']))
                            else:
                                error_msg = f"status {resp.status_code}"
                        except Exception:
                            error_msg = f"status {resp.status_code}: {resp.text[:100]}"
                        return {"success": False, "error": error_msg}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            # Test with specified model
            tasks = [probe_model(model) for _ in range(concurrency)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success = 0
            error_msg = None
            for r in results:
                if isinstance(r, Exception):
                    error_msg = str(r)
                elif isinstance(r, dict):
                    if r.get('success'):
                        success += 1
                    else:
                        if not error_msg:
                            error_msg = r.get('error', 'Unknown error')


            # Determine max concurrency
            if success == concurrency:
                max_concurrency = concurrency
                error_msg = None
            elif success > 0:
                max_concurrency = success
                error_msg = None
            else:
                max_concurrency = 0

            return {
                "provider": provider_name,
                "model": model,
                "max_concurrency": max_concurrency,
                "error": error_msg
            }
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/test/token/model")
async def api_test_token_model(request: Request):
    """Run token test for a specific model (SSE stream)."""
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body") from e

    key = (body.get("key") or "").strip()
    provider_name = (body.get("provider") or "").lower()
    model = (body.get("model") or "").strip()

    if not key:
        raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY, message="Missing key")
    if not model:
        raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY, message="Missing model")

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    provider_name, provider_obj = await resolve_provider(
        key=key,
        provider_name=provider_name or None,
        timeout=_app_mod.config.get("check", {}).get("timeout_seconds", 30),
        proxy=proxy,
        providers=_app_mod.PROVIDERS,
        detect_provider_fn=_app_mod.detect_provider,
    )

    # Run test
    try:
        async with httpx.AsyncClient(timeout=_app_mod.config["test"]["concurrency_timeout_seconds"], proxy=proxy) as client:
            headers = provider_obj.build_headers(key)
            headers["Content-Type"] = "application/json"

            chat_url = build_chat_url(provider_obj)

            # Send a large token value to get the actual limit from error
            large_tokens = 1000000
            resp = await client.post(
                chat_url,
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": large_tokens}
            )

            if resp.status_code == 200:
                return {
                    "provider": provider_name,
                    "model": model,
                    "max_tokens": large_tokens,
                    "error": None
                }

            # Parse error to extract limit
            try:
                error_data = resp.json()
                error_msg = error_data.get("error", {}).get("message", "")

                # Try to find limit after 'maximum' or 'max' keyword
                max_match = re.search(r'(?:maximum|max)\s+(?:is\s+)?(\d+)', error_msg, re.IGNORECASE)
                if max_match:
                    limit = int(max_match.group(1))
                    if limit >= 100:
                        return {
                            "provider": provider_name,
                            "model": model,
                            "max_tokens": limit,
                            "error": None
                        }

                # Fallback: find numbers and use the second largest
                numbers = re.findall(r'\d+', error_msg)
                if len(numbers) >= 2:
                    sorted_nums = sorted({int(n) for n in numbers}, reverse=True)
                    for num in sorted_nums:
                        if num >= 100:
                            return {
                                "provider": provider_name,
                                "model": model,
                                "max_tokens": num,
                                "error": None
                            }
                elif numbers:
                    num = int(numbers[0])
                    if num >= 100:
                        return {
                            "provider": provider_name,
                            "model": model,
                            "max_tokens": num,
                            "error": None
                        }
            except Exception:
                pass

            return {
                "provider": provider_name,
                "model": model,
                "max_tokens": None,
                "error": "Could not parse token limit"
            }
    except Exception as e:
        return {"error": str(e)}
