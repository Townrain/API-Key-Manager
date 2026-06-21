from .base import ProviderBase


class GrokProvider(ProviderBase):
    name = "grok"
    base_url = "https://api.x.ai"
    check_endpoint = "/v1/models"
