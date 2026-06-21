from .base import ProviderBase


class CerebrasProvider(ProviderBase):
    name = "cerebras"
    base_url = "https://api.cerebras.ai/v1"
    check_endpoint = "/models"
