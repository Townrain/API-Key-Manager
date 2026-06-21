"""Load custom providers from config.yaml."""
import yaml
import logging
from .base import ProviderBase

logger = logging.getLogger(__name__)


def load_custom_providers() -> dict[str, ProviderBase]:
    """Load custom providers from config.yaml providers.custom section."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"Failed to load config.yaml: {e}")
        return {}

    custom_providers = config.get("providers", {}).get("custom", [])
    if not custom_providers:
        return {}

    result = {}
    for provider_config in custom_providers:
        try:
            provider = _create_provider_from_config(provider_config)
            result[provider.name] = provider
        except Exception as e:
            logger.warning(f"Failed to load custom provider: {e}")

    return result


def _create_provider_from_config(config: dict) -> ProviderBase:
    """Create a ProviderBase instance from config dict."""
    # Validate required fields
    required = ["name", "base_url", "check_endpoint"]
    for field in required:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")

    # Create dynamic provider class
    name = config["name"]
    base_url = config["base_url"]
    check_endpoint = config["check_endpoint"]
    display_name = config.get("display_name", name)
    key_prefixes = config.get("key_prefixes", [])
    error_signatures = config.get("error_signatures", [])
    website_url = config.get("website_url", "")
    docs_url = config.get("docs_url", "")
    chat_endpoint = config.get("chat_endpoint", "/chat/completions")
    auth_type = config.get("auth_type", "bearer")

    # Build headers based on auth_type
    if auth_type == "bearer":
        def build_headers(key):
            return {"Authorization": f"Bearer {key}"}
    elif auth_type == "x-api-key":
        def build_headers(key):
            return {"x-api-key": key}
    elif auth_type == "query_param":
        def build_headers(key):
            return {}  # Key will be added to URL
    else:
        def build_headers(key):
            return {"Authorization": f"Bearer {key}"}

    # Create class dynamically
    provider_class = type(
        f"{name.title().replace('-', '')}Provider",
        (ProviderBase,),
        {
            "name": name,
            "base_url": base_url,
            "check_endpoint": check_endpoint,
            "display_name": display_name,
            "key_prefixes": key_prefixes,
            "error_signatures": error_signatures,
            "website_url": website_url,
            "docs_url": docs_url,
            "chat_endpoint": chat_endpoint,
            "build_headers": build_headers,
        }
    )

    return provider_class()


def save_custom_provider(config: dict) -> None:
    """Save a custom provider to config.yaml."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        full_config = {}

    if "providers" not in full_config:
        full_config["providers"] = {}
    if "custom" not in full_config["providers"]:
        full_config["providers"]["custom"] = []

    # Check if provider already exists
    custom = full_config["providers"]["custom"]
    for i, p in enumerate(custom):
        if p.get("name") == config["name"]:
            custom[i] = config
            break
    else:
        custom.append(config)

    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(full_config, f, default_flow_style=False, allow_unicode=True)


def remove_custom_provider(name: str) -> bool:
    """Remove a custom provider from config.yaml."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            full_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return False

    custom = full_config.get("providers", {}).get("custom", [])
    for i, p in enumerate(custom):
        if p.get("name") == name:
            custom.pop(i)
            with open("config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(full_config, f, default_flow_style=False, allow_unicode=True)
            return True

    return False
