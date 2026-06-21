from .base import ProviderBase


class ZAIProvider(ProviderBase):
    name = "zai"
    base_url = "https://api.z.ai/api/paas/v4"
    check_endpoint = "/models"
