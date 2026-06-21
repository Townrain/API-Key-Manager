from .base import ProviderBase


class PPIOProvider(ProviderBase):
    name = "ppio"
    base_url = "https://api.ppinfra.com/v3/openai"
    check_endpoint = "/models"
