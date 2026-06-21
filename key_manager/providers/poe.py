from .base import ProviderBase


class PoeProvider(ProviderBase):
    name = "poe"
    base_url = "https://api.poe.com/v1"
    check_endpoint = "/models"
