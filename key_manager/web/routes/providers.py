"""Provider management routes."""

from fastapi import APIRouter, Request

from key_manager.providers import (
    get_display_name,
    DISPLAY_NAMES,
    PROVIDER_WEBSITES,
    KEY_PREFIX_MAP,
)
from key_manager.i18n import t
from key_manager.errors import ErrorCode, ValidationError
from key_manager.api_models import (
    ProviderInfo as ProviderInfoModel,
    ProvidersResponse,
    ProviderDetail,
    ProviderDetailResponse,
)

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod

router = APIRouter(tags=["Providers"])


def _get_custom_provider_names() -> set[str]:
    """Get names of custom providers from config.yaml."""
    try:
        import yaml
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        custom = config.get("providers", {}).get("custom", [])
        return {p["name"] for p in custom if "name" in p}
    except Exception:
        return set()


@router.get("/api/providers", response_model=ProvidersResponse)
async def api_providers():
    """List all registered providers."""
    provider_list: list[ProviderInfoModel] = []
    for name, p in _app_mod.PROVIDERS.items():
        prefix = ""
        for pf, providers in KEY_PREFIX_MAP.items():
            if name in providers:
                prefix = pf
                break
        provider_list.append(ProviderInfoModel(
            name=name,
            display_name=get_display_name(name),
            prefix=prefix or "-",
            base_url=getattr(p, "base_url", ""),
            type="ai",
        ))
    return ProvidersResponse(providers=provider_list, total=len(provider_list))


@router.get("/api/providers/detail", response_model=ProviderDetailResponse)
async def api_providers_detail():
    """Get detailed provider information including website and docs URLs."""
    detail_list: list[ProviderDetail] = []
    for name in _app_mod.PROVIDERS:
        website = PROVIDER_WEBSITES.get(name, {})
        prefix = ""
        for pf, providers in KEY_PREFIX_MAP.items():
            if name in providers:
                prefix = pf
                break
        detail_list.append(ProviderDetail(
            name=name,
            display_name=get_display_name(name),
            prefix=prefix or "-",
            base_url=getattr(_app_mod.PROVIDERS[name], "base_url", ""),
            website_url=website.get("url", ""),
            docs_url=website.get("docs", ""),
            website_name=website.get("name", get_display_name(name)),
        ))
    return ProviderDetailResponse(providers=detail_list, total=len(detail_list))


@router.get("/api/providers/{provider_name}")
async def api_providers_get(provider_name: str):
    """Get a specific provider's configuration."""
    provider = _app_mod.PROVIDERS.get(provider_name)
    if not provider:
        raise ValidationError(code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                            message=f"Provider '{provider_name}' not found")
    
    return {
        "name": provider.name,
        "display_name": provider.display_name or provider.name,
        "base_url": provider.base_url,
        "check_endpoint": provider.check_endpoint,
        "chat_endpoint": provider.chat_endpoint,
        "key_prefixes": provider.key_prefixes,
        "error_signatures": provider.error_signatures,
        "website_url": provider.website_url,
        "docs_url": provider.docs_url,
        "source": "builtin" if provider_name not in _get_custom_provider_names() else "custom",
    }


@router.post("/api/providers")
async def api_providers_create(request: Request):
    """Create a new custom provider."""
    from key_manager.providers.config_providers import save_custom_provider, _create_provider_from_config
    from key_manager.providers import _PROVIDER_REGISTRY
    
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body")
    
    # Validate required fields
    required = ["name", "base_url", "check_endpoint"]
    for field in required:
        if field not in body:
            raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY,
                                message=f"Missing required field: {field}")
    
    # Check if provider already exists
    if body["name"] in _PROVIDER_REGISTRY:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Provider '{body['name']}' already exists")
    
    try:
        # Save to config
        save_custom_provider(body)
        
        # Create and register provider
        provider = _create_provider_from_config(body)
        _PROVIDER_REGISTRY[provider.name] = provider
        
        return {"success": True, "provider": body}
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Failed to create provider: {str(e)}")


@router.put("/api/providers/{provider_name}")
async def api_providers_update(provider_name: str, request: Request):
    """Update a custom provider's configuration."""
    from key_manager.providers.config_providers import save_custom_provider, _create_provider_from_config
    from key_manager.providers import _PROVIDER_REGISTRY
    
    # Check if provider exists
    if provider_name not in _PROVIDER_REGISTRY:
        raise ValidationError(code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                            message=f"Provider '{provider_name}' not found")
    
    # Check if it's a custom provider
    if provider_name not in _get_custom_provider_names():
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Cannot modify builtin provider '{provider_name}'")
    
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body")
    
    try:
        # Update config
        body["name"] = provider_name
        save_custom_provider(body)
        
        # Recreate provider
        provider = _create_provider_from_config(body)
        _PROVIDER_REGISTRY[provider_name] = provider
        
        return {"success": True, "provider": body}
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Failed to update provider: {str(e)}")


@router.delete("/api/providers/{provider_name}")
async def api_providers_delete(provider_name: str):
    """Delete a custom provider."""
    from key_manager.providers.config_providers import remove_custom_provider
    from key_manager.providers import _PROVIDER_REGISTRY
    
    # Check if provider exists
    if provider_name not in _PROVIDER_REGISTRY:
        raise ValidationError(code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                            message=f"Provider '{provider_name}' not found")
    
    # Check if it's a custom provider
    if provider_name not in _get_custom_provider_names():
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Cannot delete builtin provider '{provider_name}'")
    
    try:
        # Remove from config
        remove_custom_provider(provider_name)
        
        # Remove from registry
        del _PROVIDER_REGISTRY[provider_name]
        
        return {"success": True}
    except Exception as e:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT,
                            message=f"Failed to delete provider: {str(e)}")


@router.post("/api/providers/{provider_name}/test")
async def api_providers_test(provider_name: str):
    """Test a provider's connectivity."""
    import httpx
    
    provider = _app_mod.PROVIDERS.get(provider_name)
    if not provider:
        raise ValidationError(code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                            message=f"Provider '{provider_name}' not found")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Try to get models
            models = await provider.get_models(client, "test-key")
            return {
                "success": True,
                "provider": provider_name,
                "models_count": len(models),
                "sample_models": models[:5] if models else [],
            }
    except Exception as e:
        return {
            "success": False,
            "provider": provider_name,
            "error": str(e),
        }
