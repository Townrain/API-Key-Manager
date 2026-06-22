"""Key validation check routes."""

import asyncio

import httpx
from key_manager.web.utils import build_chat_url, resolve_provider
from fastapi import APIRouter, Form, Request

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import (
    CheckBatchItem,
    CheckBatchRequest,
    CheckBatchResponse,
    CheckBatchResult,
    CheckBatchSummary,
    CheckSingleRequest,
    CheckSingleResponse,
)
from key_manager.detector import detect_by_prefix
from key_manager.errors import ErrorCode, ValidationError
from key_manager.i18n import t
from key_manager.logger import project_logger
from key_manager.parser import mask_key
from key_manager.providers import get_display_name
from key_manager.providers.base import CheckResult, simplify_error
from key_manager.proxy import get_proxy
from key_manager.ssrf import get_allowed_domains, validate_custom_base_url
from key_manager.url_override import custom_base_url
from key_manager.web.progress import _make_progress_callback
from key_manager.webhook import WebhookEvent, webhook_manager

router = APIRouter(tags=["Check"])


async def _check_model_specific(
    client: httpx.AsyncClient,
    provider_obj,
    key: str,
    model_name: str,
) -> 'CheckResult':
    """Check a specific model against a provider.

    Extracted to eliminate duplication in api_check_single.
    """
    import time

    from key_manager.providers.base import CheckResult

    headers = provider_obj.build_headers(key)
    headers["Content-Type"] = "application/json"
    chat_url = build_chat_url(provider_obj)
    start = time.monotonic()
    try:
        resp = await client.post(
            chat_url,
            headers=headers,
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
        )
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return CheckResult(valid=True, status_code=200, latency_ms=latency, error=None)
        else:
            error_msg = f"status {resp.status_code}"
            try:
                error_msg = resp.json().get("error", {}).get("message", error_msg)
            except Exception:
                pass
            return CheckResult(valid=False, status_code=resp.status_code, latency_ms=latency, error=error_msg)
    except Exception as e:
        return CheckResult(valid=False, status_code=None, latency_ms=(_time.monotonic() - start) * 1000, error=str(e))


@router.post("/api/check")
async def api_check(
    provider: str = Form(None),
    status: str = Form(None),
    request: Request = None,
):
    """Run a validation check against all keys (synchronous - returns results directly)."""
    # Support both form data and JSON body
    body_json = None
    if request and request.method == "POST":
        try:
            body_json = await request.json()
        except Exception:
            pass
    # Support both form data and JSON body
    p = provider or (body_json or {}).get("provider")
    s = status or (body_json or {}).get("status")

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    results = await _app_mod.validate_keys(
        keys_file=_app_mod.config["storage"]["keys_file"],
        results_file=_app_mod.config["storage"]["check_results_file"],
        logs_dir=_app_mod.config["storage"]["logs_dir"],
        concurrency=_app_mod.config["check"]["concurrency"],
        timeout=_app_mod.config["check"]["timeout_seconds"],
        proxy=proxy,
        provider_filter=p or None,
        status_filter=s or None,
        progress_callback=_make_progress_callback(),
    )
    project_logger.log_web_action("check_all", f"total={results.get('total', 0)}")

    # Dispatch webhook
    task = asyncio.create_task(
        webhook_manager.dispatch(
            WebhookEvent.BATCH_CHECK_COMPLETED,
            {"total": results.get("total", 0)},
        )
    )
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)  # Suppress unhandled exception warning

    return results


@router.post("/api/check/single", response_model=CheckSingleResponse)
async def api_check_single(body: CheckSingleRequest):
    """Check validity of a single API key."""
    key = (body.key or "").strip()
    provider_name = (body.provider or "").strip()

    custom_url = body.custom_base_url
    if custom_url:
        allowed_domains = get_allowed_domains(_app_mod.PROVIDERS)
        validate_custom_base_url(custom_url, allowed_domains)
        custom_base_url.set(custom_url)
    if not key:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    # Resolve provider (detect if needed, validate, get provider object)
    provider_name, provider_obj = await resolve_provider(
        key=key,
        provider_name=provider_name,
        timeout=_app_mod.config.get("check", {}).get("timeout_seconds", 30),
        proxy=get_proxy(_app_mod.config.get("proxy")),
        providers=_app_mod.PROVIDERS,
        detect_provider_fn=_app_mod.detect_provider,
    )

    proxy = get_proxy(_app_mod.config.get("proxy")) or None

    try:
        async with httpx.AsyncClient(
            timeout=_app_mod.config["check"]["timeout_seconds"],
            proxy=proxy,
            follow_redirects=False,
        ) as client:

            # If provider was auto-detected, the detection already validated the key
            # Only call check() if provider was manually specified
            model_name = body.model
            if body.provider:
                if model_name:
                    result = await _check_model_specific(client, provider_obj, key, model_name)
                else:
                    result = await provider_obj.check(client, key)
            else:
                # Provider was auto-detected, still need to validate the key
                if model_name:
                    result = await _check_model_specific(client, provider_obj, key, model_name)
                else:
                    result = await provider_obj.check(client, key)
            # Attempt balance query
            balance = None
            if result.valid and hasattr(provider_obj, "get_balance"):
                try:
                    bal = await provider_obj.get_balance(client, key)
                    if bal.supported and bal.balance is not None:
                        balance = {"balance": bal.balance, "currency": bal.currency}
                except Exception:
                    pass

            # Attempt models query
            models: list[str] = []
            if result.valid and hasattr(provider_obj, "get_models"):
                try:
                    models = await provider_obj.get_models(client, key) or []
                except Exception:
                    pass

            error_type = None
            if not result.valid:
                if result.status_code in (401, 403):
                    error_type = "invalid_key"
                elif result.status_code == 429:
                    error_type = "rate_limited"
                elif result.status_code == 402:
                    error_type = "insufficient_balance"

            status_str = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")

            project_logger.log_web_action("check_single", f"{mask_key(key)} {provider_name}: {status_str}")

            # Simplify error message for readability
            simplified_error = simplify_error(result.error, result.status_code) if result.error else None

            return CheckSingleResponse(
                key_masked=mask_key(key),
                provider=provider_name,
                display_name=get_display_name(provider_name),
                status=status_str,
                status_code=result.status_code,
                latency_ms=result.latency_ms,
                error=simplified_error,
                error_type=error_type,
                balance=balance,
                models=models,
            )
    finally:
        custom_base_url.set(None)


@router.post("/api/check/batch", response_model=CheckBatchResponse)
async def api_check_batch(body: CheckBatchRequest):
    """Check validity of multiple keys in batch."""
    if not body.keys:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    results: list[CheckBatchResult] = []
    summary = CheckBatchSummary()

    sem = asyncio.Semaphore(body.concurrency or 50)

    async def _check_one(item: CheckBatchItem):
        key = (item.key or "").strip()
        provider_name = (item.provider or "").strip()

        if not key:
            return CheckBatchResult(
                key_masked="(empty)",
                provider="unknown",
                status="error",
                error="Empty key provided",
            )

        if not provider_name:
            # Use detect_provider for robust detection
            try:
                async with httpx.AsyncClient(timeout=10, proxy=proxy) as detect_client:
                    provider_name = await _app_mod.detect_provider(detect_client, key)
            except Exception:
                pass
            if not provider_name or provider_name == 'unknown':
                candidates = detect_by_prefix(key)
                provider_name = candidates[0] if candidates else "unknown"
        else:
            provider_name = provider_name.lower()

        provider_obj = _app_mod.PROVIDERS.get(provider_name)
        if not provider_obj:
            return CheckBatchResult(
                key_masked=mask_key(key),
                provider=provider_name,
                status="error",
                error=f"Unknown provider: {provider_name}",
            )

        async with sem:
            async with httpx.AsyncClient(
                timeout=body.timeout or 10,
                proxy=proxy,
                follow_redirects=False,
            ) as client:
                result = await provider_obj.check(client, key)

        status_str = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")
        return CheckBatchResult(
            key_masked=mask_key(key),
            provider=provider_name,
            status=status_str,
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            error=result.error,
            error_type=getattr(result, "error_type", None),
        )

    tasks = [_check_one(item) for item in body.keys]
    batch_results = await asyncio.gather(*tasks)

    for r in batch_results:
        results.append(r)
        if r.status == "valid":
            summary.valid += 1
        elif r.status == "invalid":
            summary.invalid += 1
        else:
            summary.error += 1

    summary.total = len(batch_results)
    project_logger.log_web_action("check_batch", f"total={summary.total}, valid={summary.valid}")

    return CheckBatchResponse(results=results, summary=summary)
