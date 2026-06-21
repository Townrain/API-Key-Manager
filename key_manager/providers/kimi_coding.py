from .base import ProviderBase


class KimiCodingProvider(ProviderBase):
    """Kimi Coding Plan provider."""
    name = "kimi-coding"
    base_url = "https://api.kimi.com/coding/v1"
    check_endpoint = "/models"
