from .base import ProviderBase


class MistralProvider(ProviderBase):
    name = "mistral"
    base_url = "https://api.mistral.ai"
    check_endpoint = "/v1/models"
