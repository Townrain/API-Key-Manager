"""Model management routes."""

import asyncio

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import ModelsResponse
from key_manager.detector import detect_by_prefix
from key_manager.errors import ErrorCode, ValidationError
from key_manager.i18n import t
from key_manager.providers.models_registry import PROVIDER_MODELS
from key_manager.proxy import get_proxy

router = APIRouter(tags=["Models"])


@router.get("/api/models", response_model=ModelsResponse)
async def api_models(
    provider: str = Query(None, description="Provider name"),
    type_filter: str = Query("all", description="Model type filter"),
    key: str = Query(None, description="API key for live model fetch"),
):
    """Get available models for a provider (static or live)."""
    provider_name = (provider or "").lower()

    if not provider_name:
        # Try to detect provider from key if provided
        if key:
            proxy = get_proxy(_app_mod.config.get("proxy")) or None
            async with httpx.AsyncClient(
                timeout=_app_mod.config["check"]["timeout_seconds"],
                proxy=proxy,
            ) as client:
                detected = await _app_mod.detect_provider(client, key)
            if detected and detected != 'unknown' and detected in _app_mod.PROVIDERS:
                provider_name = detected
                provider_obj = _app_mod.PROVIDERS[provider_name]
                # Fall through to live model fetch below
            else:
                return ModelsResponse(
                    provider="unknown",
                    models=[],
                    total=0,
                    type_filter=type_filter,
                    source=None,
                    hint="未找到有效的 Key，请检查 Key 是否正确或 Provider 是否支持",
                )
        else:
            # No key provided, return all static models from PROVIDER_MODELS
            all_models: list[str] = []
            for provider_models in PROVIDER_MODELS.values():
                all_models.extend(provider_models)
            return ModelsResponse(
                provider="all",
                models=sorted(set(all_models)),
                total=len(set(all_models)),
                type_filter=type_filter,
                source="static",
            )

    provider_obj = _app_mod.PROVIDERS.get(provider_name)
    if not provider_obj:
        return ModelsResponse(
            provider=provider_name,
            models=[],
            total=0,
            type_filter=type_filter,
            source=None,
            hint="Provider not found",
        )

    models: list[str] = []
    source = "static"

    if key and hasattr(provider_obj, "get_models"):
        proxy = get_proxy(_app_mod.config.get("proxy")) or None
        async with httpx.AsyncClient(
            timeout=_app_mod.config["check"]["timeout_seconds"],
            proxy=proxy,
        ) as client:
            try:
                models = await provider_obj.get_models(client, key) or []
                source = "api"
            except Exception:
                pass

    if not models and hasattr(provider_obj, "models"):
        models = getattr(provider_obj, "models", [])

    # Fallback to static models from PROVIDER_MODELS (Cherry Studio sync)
    if not models:
        models = PROVIDER_MODELS.get(provider_name, [])
    # Apply type filter (if model_capabilities module is available)
    filtered = models
    try:
        from key_manager.model_capabilities import detector
        await detector.load()
        if type_filter == "vision":
            filtered = [m for m in models if detector.is_vision_model(m)]
        elif type_filter in ("tool", "tooluse"):
            filtered = [m for m in models if detector.is_tool_model(m)]
        elif type_filter == "reasoning":
            filtered = [m for m in models if detector.is_reasoning_model(m)]
    except Exception:
        pass

    return ModelsResponse(
        provider=provider_name,
        models=filtered,
        total=len(filtered),
        type_filter=type_filter,
        source=source,
    )


@router.get("/api/models/capabilities")
async def api_models_capabilities(
    models: str = Query(..., description="Comma-separated model IDs"),
):
    """Get capabilities for a list of model IDs."""
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    if not model_list:
        return {"capabilities": {}}

    try:
        from key_manager.model_capabilities import detector
        await detector.load()

        result = {}
        for model_id in model_list:
            result[model_id] = detector.get_model_capabilities(model_id)

        return {"capabilities": result}
    except Exception as e:
        return {"capabilities": {}, "error": str(e)}


@router.post("/api/models/check")
async def api_models_check(request: Request):
    """Live model availability check (SSE stream)."""
    try:
        body = await request.json()
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body") from e

    provider_name = (body.get("provider") or "").lower()
    key = (body.get("key") or "").strip()
    if not key:
        raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY, message=t("VALIDATION_MISSING_KEY"))

    proxy = get_proxy(_app_mod.config.get("proxy")) or None
    provider_obj = None
    models: list[str] = []
    source = "api"

    # Step 1: Find provider and get models
    if provider_name:
        provider_obj = _app_mod.PROVIDERS.get(provider_name)
        if provider_obj:
            async with httpx.AsyncClient(timeout=_app_mod.config["check"]["timeout_seconds"], proxy=proxy) as client:
                try:
                    models = await provider_obj.get_models(client, key) or []
                except Exception:
                    pass
    else:
        # Use detect_provider for robust auto-detection
        async with httpx.AsyncClient(timeout=_app_mod.config["check"]["timeout_seconds"], proxy=proxy) as client:
            detected = await _app_mod.detect_provider(client, key)
            if detected and detected != 'unknown':
                provider_name = detected
                provider_obj = _app_mod.PROVIDERS.get(provider_name)
                if provider_obj:
                    try:
                        models = await provider_obj.get_models(client, key) or []
                    except Exception:
                        pass

    # Step 2: Fallback to static models from PROVIDER_MODELS
    if not models and provider_obj:
        source = "static"
        models = PROVIDER_MODELS.get(provider_name, [])
    if not provider_name:
        candidates = detect_by_prefix(key)
        provider_name = candidates[0] if candidates else "unknown"
        provider_obj = _app_mod.PROVIDERS.get(provider_name)

    # Step 3: SSE response
    if not models:
        async def empty():
            yield f'data: {{"type":"complete","provider":"{provider_name}","available":0,"total":0,"source":"{source}"}}\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    async def stream():
        # Phase 1: Report models found
        yield f'data: {{"type":"progress","current":0,"total":{len(models)},"model":"","mode":"parallel"}}\n\n'

        # Phase 2: Check all models
        available_count = 0
        timeout_count = 0
        all_available_models = set()
        failed_models = []

        async def check_model(http, model):
            """Use provider's _probe_model method with 10s timeout."""
            try:
                result = await asyncio.wait_for(
                    provider_obj._probe_model(http, provider_obj.build_headers(key), model),
                    timeout=10.0
                )
                return model, 200 if result else -2
            except asyncio.TimeoutError:
                return model, -1
            except httpx.TimeoutException:
                return model, -1
            except Exception:
                return model, -2

        async with httpx.AsyncClient(proxy=proxy) as http:
            # Step 1: Parallel check with dynamic batch_size
            # Start from 5, +1 on each success, stay same on failure
            batch_size = 5
            i = 0
            while i < len(models):
                batch = models[i:i+batch_size]
                yield f'data: {{"type":"progress","current":{i+1},"total":{len(models)},"model":"{batch[0]}","mode":"parallel","batch_size":{len(batch)}}}\n\n'

                results = await asyncio.gather(*[check_model(http, m) for m in batch])

                batch_success = True
                for model, code in results:
                    if code == 200:
                        available_count += 1
                        all_available_models.add(model)
                        yield f'data: {{"type":"result","model":"{model}","available":true,"status":"available"}}\n\n'
                    else:
                        failed_models.append(model)
                        batch_success = False
                        yield f'data: {{"type":"model_timeout","model":"{model}"}}\n\n'

                # Adjust batch_size: +1 if all success, stay same if any failure
                if batch_success:
                    batch_size += 1
                i += len(batch)
            # Step 2: Serial retry failed models
            if failed_models:
                yield 'data: {"type":"serial_mode","reason":"retry_failed"}\n\n'
                await asyncio.sleep(0.5)

                for model in failed_models[:]:
                    if model in all_available_models:
                        continue

                    _, code = await check_model(http, model)

                    if code == 200:
                        available_count += 1
                        all_available_models.add(model)
                        failed_models.remove(model)
                        yield f'data: {{"type":"result","model":"{model}","available":true,"status":"available","retry":true}}\n\n'
                    else:
                        timeout_count += 1
                        yield f'data: {{"type":"model_timeout","model":"{model}","retry":true}}\n\n'

        # Final summary
        yield f'data: {{"type":"complete","provider":"{provider_name}","available":{available_count},"total":{len(models)},"timeout":{timeout_count},"source":"{source}"}}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})
