from .base import ProviderBase


class PerplexityProvider(ProviderBase):
    name = "perplexity"
    base_url = "https://api.perplexity.ai"
    check_endpoint = "/v1/models"
