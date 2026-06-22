"""Miscellaneous routes: proxy, logs, progress, webhooks, signature report."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import (
    LogsResponse,
    OperationEntry,
    OperationsResponse,
    ProgressResponse,
    ProxyResponse,
)
from key_manager.errors import ErrorCode, ValidationError
from key_manager.logger import project_logger
from key_manager.proxy import get_proxy
from key_manager.web.progress import _progress_tracker, _sse_progress_event_generator
from key_manager.webhook import webhook_manager

router = APIRouter(tags=["Proxy", "Logs", "Progress", "Webhooks"])


# ---
# PROXY
# ---

@router.get("/api/proxy", tags=["Proxy"], response_model=ProxyResponse)
async def api_proxy():
    """Get proxy configuration status."""
    config_proxy = _app_mod.config.get("proxy")
    proxy = get_proxy(config_proxy)

    if proxy:
        # Check if it's from config or auto-detected
        if config_proxy is not None and config_proxy != "":
            source = "config"
        else:
            source = "auto"
    else:
        proxy = None
        source = "none"

    return ProxyResponse(proxy=proxy, source=source)


# ---
# LOGS
# ---

@router.get("/api/logs", tags=["Logs"], response_model=LogsResponse)
async def api_logs():
    """Get recent log entries."""
    logs = project_logger.get_recent_logs()
    return LogsResponse(logs=logs)  # Return strings directly for frontend compatibility


@router.get("/api/logs/operations", tags=["Logs"], response_model=OperationsResponse)
async def api_logs_operations():
    """Get recent operation log entries."""
    operations = project_logger.get_operations_log()
    return OperationsResponse(operations=[OperationEntry(**entry) for entry in operations])


@router.delete("/api/logs", tags=["Logs"])
async def api_logs_clear(date: str = None):
    """Clear main log file for specified date (default: today).

    Args:
        date: Date string in YYYY-MM-DD format (optional, default: today)

    Returns:
        dict with success status and details
    """
    result = project_logger.clear_main_log(date)
    return result


# ---
# PROGRESS
# ---

@router.get("/api/progress", tags=["Progress"], response_model=ProgressResponse)
async def api_progress():
    """Get current progress of long-running operations."""
    return _progress_tracker.snapshot()


@router.get("/api/progress/stream", tags=["Progress"])
async def api_progress_stream():
    """Stream progress updates via SSE."""
    return StreamingResponse(
        _sse_progress_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---
# WEBHOOKS
# ---

@router.get("/api/webhooks", tags=["Webhooks"])
async def api_webhooks_list():
    """List all configured webhooks."""
    return webhook_manager.list_all()


@router.post("/api/webhooks", tags=["Webhooks"])
async def api_webhooks_create(request: Request):
    """Create a new webhook."""
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body") from e
    webhook_id = webhook_manager.register(
        url=body.get('url', ''),
        events=body.get('events'),
        secret=body.get('secret'),
        active=body.get('active', True),
        max_retries=body.get('max_retries', 3),
    )
    return {"success": True, "webhook_id": webhook_id}


@router.get("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_get(webhook_id: str):
    """Get a specific webhook."""
    webhook = webhook_manager.get(webhook_id)
    if not webhook:
        raise ValidationError(code=ErrorCode.VALIDATION_FILE_NOT_FOUND, message="Webhook not found")
    return webhook


@router.put("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_update(webhook_id: str, request: Request):
    """Update a webhook."""
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body") from e
    webhook_manager.update(webhook_id, **body)
    return {"success": True}


@router.delete("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_delete(webhook_id: str):
    """Delete a webhook."""
    webhook_manager.unregister(webhook_id)
    return {"success": True}


@router.get("/api/webhooks/log/deliveries", tags=["Webhooks"])
async def api_webhooks_log_deliveries():
    """Get webhook delivery logs."""
    return webhook_manager.get_delivery_log()


@router.delete("/api/webhooks/log/deliveries", tags=["Webhooks"])
async def api_webhooks_log_deliveries_clear():
    """Clear webhook delivery logs."""
    webhook_manager.clear_delivery_log()
    return {"success": True}


# ---
# SIGNATURE REPORT
# ---

@router.get("/api/signature-report")
async def api_signature_report():
    """Generate signature verification report dynamically."""
    import re

    import httpx

    from key_manager.providers import PROVIDER_ERROR_SIGNATURES, PROVIDERS

    INVALID_KEY = "sk-invalid-test-key-for-signature-verification-12345"
    TIMEOUT_SECONDS = 10.0

    def extract_signatures(body: str) -> list[str]:
        body_lower = body.lower()
        words = re.findall(r'[a-z0-9][a-z0-9_-]{2,}', body_lower)
        return list(set(words))

    results = []
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        for provider_name, provider in PROVIDERS.items():
            try:
                result = await asyncio.wait_for(
                    provider.probe(client, INVALID_KEY),
                    timeout=TIMEOUT_SECONDS
                )
                status_code = result.status_code
                response_body = result.response_body or ""
                error = result.error
                valid = result.valid
            except asyncio.TimeoutError:
                status_code = None
                response_body = ""
                error = "timeout"
                valid = False
            except Exception as e:
                status_code = None
                response_body = ""
                error = str(e)
                valid = False

            # Verify signatures
            body_lower = response_body.lower()
            current_sigs = PROVIDER_ERROR_SIGNATURES.get(provider_name, [])
            matched = [s for s in current_sigs if s.lower() in body_lower]
            missing = [s for s in current_sigs if s.lower() not in body_lower]

            # Find new signatures
            extracted = extract_signatures(response_body)
            known = {s.lower() for s in current_sigs}
            new_sigs = [s for s in extracted if s not in known and len(s) > 3][:10]

            # Find conflicts
            conflicts = []
            for other_name, other_sigs in PROVIDER_ERROR_SIGNATURES.items():
                if other_name == provider_name:
                    continue
                for sig in other_sigs:
                    if sig.lower() in body_lower:
                        conflicts.append({"signature": sig, "other_provider": other_name})

            results.append({
                "provider": provider_name,
                "status_code": status_code,
                "error": error,
                "valid": valid,
                "response_body": response_body[:500],
                "unique_signatures": {
                    "total": len(current_sigs),
                    "matched": matched,
                    "missing": missing,
                    "match_rate": len(matched) / len(current_sigs) if current_sigs else 0,
                },
                "new_signatures": new_sigs,
                "conflicts": conflicts,
            })

    # Generate summary
    total = len(results)
    successful = sum(1 for r in results if r["status_code"] is not None)
    full_match = sum(1 for r in results if r["unique_signatures"]["match_rate"] == 1.0)
    partial_match = sum(1 for r in results if 0 < r["unique_signatures"]["match_rate"] < 1.0)
    no_match = sum(1 for r in results if r["unique_signatures"]["match_rate"] == 0)
    has_conflicts = sum(1 for r in results if r["conflicts"])
    has_new_sigs = sum(1 for r in results if r["new_signatures"])

    return {
        "summary": {
            "total_providers": total,
            "successful_tests": successful,
            "full_match": full_match,
            "partial_match": partial_match,
            "no_match": no_match,
            "has_conflicts": has_conflicts,
            "has_new_signatures": has_new_sigs,
        },
        "results": results,
    }
