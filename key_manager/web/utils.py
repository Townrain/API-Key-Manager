"""Shared utility functions for the web module.

This module contains small, reusable helpers used across multiple
web routes and modules.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from key_manager.providers.base import ProviderBase


def build_chat_url(provider: "ProviderBase") -> str:
    """Build chat completions URL from provider's check_endpoint.

    Extracts version prefix (e.g., ``/v1``) from ``check_endpoint`` and
    constructs the full chat completions URL by appending ``/chat/completions``.

    Args:
        provider: Provider object with ``check_endpoint`` and
            ``get_base_url()`` methods.

    Returns:
        Full chat completions URL string.

    Examples:
        >>> # Provider with versioned endpoint
        >>> provider.check_endpoint = "/v1/models"
        >>> build_chat_url(provider)
        'https://api.example.com/v1/chat/completions'

        >>> # Provider without version prefix
        >>> provider.check_endpoint = "/models"
        >>> build_chat_url(provider)
        'https://api.example.com/chat/completions'
    """
    version_match = re.match(r"(/v\d+)", provider.check_endpoint or "")
    version_prefix = version_match.group(1) if version_match else ""
    return f"{provider.get_base_url()}{version_prefix}/chat/completions"


async def resolve_provider(
    key: str,
    provider_name: str | None,
    timeout: int,
    proxy: str | None,
    providers: dict,
    detect_provider_fn,
) -> tuple[str, object]:
    """Resolve provider name and object from key.

    Handles the common pattern of:
    1. If provider_name not given, detect it from the key
    2. Validate the provider name is known
    3. Get the provider object

    Args:
        key: The API key to check
        provider_name: Explicit provider name, or None to auto-detect
        timeout: HTTP timeout in seconds for detection requests
        proxy: Optional proxy URL
        providers: Dict of provider_name -> provider_object
        detect_provider_fn: Async function to detect provider from key

    Returns:
        tuple: (provider_name, provider_obj)

    Raises:
        ValidationError: If provider cannot be determined or is unknown
    """
    import httpx

    from key_manager.errors import ErrorCode, ValidationError
    from key_manager.i18n import t

    if not provider_name:
        async with httpx.AsyncClient(timeout=timeout, proxy=proxy or None) as client:
            provider_name = await detect_provider_fn(client, key)
        if not provider_name or provider_name == 'unknown':
            raise ValidationError(
                code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                message=t("VALIDATION_PROVIDER_UNKNOWN"),
            )

    provider_name_lower = provider_name.lower()
    provider_obj = providers.get(provider_name_lower)
    if not provider_obj:
        raise ValidationError(
            code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
            message=t("VALIDATION_PROVIDER_UNKNOWN"),
        )

    return provider_name, provider_obj
