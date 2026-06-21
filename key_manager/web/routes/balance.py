"""Balance query route."""

import httpx
from fastapi import APIRouter

from key_manager.parser import mask_key
from key_manager.proxy import get_proxy
from key_manager.logger import project_logger
from key_manager.i18n import t
from key_manager.ssrf import validate_custom_base_url, get_allowed_domains
from key_manager.url_override import custom_base_url
from key_manager.errors import ErrorCode, ValidationError
from key_manager.api_models import BalanceRequest, BalanceResponse

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod

router = APIRouter(tags=["Balance"])


@router.post("/api/balance", response_model=BalanceResponse)
async def api_balance(body: BalanceRequest):
    """Query account balance for a key."""
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

    try:
        if not provider_name:
            proxy = get_proxy(_app_mod.config.get("proxy")) or None
            async with httpx.AsyncClient(timeout=_app_mod.config["check"]["timeout_seconds"], proxy=proxy) as client:
                provider_name = await _app_mod.detect_provider(client, key)
            if not provider_name or provider_name == 'unknown':
                raise ValidationError(
                    code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                    message=t("VALIDATION_PROVIDER_UNKNOWN"),
                )

        provider_name_lower = provider_name.lower()
        provider_obj = _app_mod.PROVIDERS.get(provider_name_lower)
        if not provider_obj:
            raise ValidationError(
                code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                message=t("VALIDATION_PROVIDER_UNKNOWN"),
            )

        proxy = get_proxy(_app_mod.config.get("proxy")) or None
        error = None
        balance_value = None
        currency = None
        supported = False

        if hasattr(provider_obj, "get_balance"):
            supported = True
            async with httpx.AsyncClient(
                timeout=_app_mod.config["check"]["timeout_seconds"],
                proxy=proxy,
            ) as client:
                try:
                    bal = await provider_obj.get_balance(client, key)
                    if bal.supported:
                        balance_value = bal.balance
                        currency = bal.currency
                    else:
                        supported = False
                    if bal.error:
                        error = bal.error
                except Exception as e:
                    error = str(e)
        else:
            error = "Provider does not support balance queries"

        project_logger.log_web_action("balance", f"{mask_key(key)} {provider_name}: {balance_value}")

        return BalanceResponse(
            provider=provider_name,
            supported=supported,
            balance=balance_value,
            currency=currency,
            key_masked=mask_key(key),
            error=error,
        )
    finally:
        custom_base_url.set(None)
