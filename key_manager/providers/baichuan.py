from .base import ProviderBase


class BaichuanProvider(ProviderBase):
    name = "baichuan"
    base_url = "https://api.baichuan-ai.com/v1"
    check_endpoint = "/models"
