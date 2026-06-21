"""OpenCode Zen provider - workspace platform with BYOK and subscriptions."""
from .base import ProviderBase


class OpenCodeZenProvider(ProviderBase):
    name = "opencode-zen"
    base_url = "https://opencode.ai/zen"
    check_endpoint = "/v1/models"
