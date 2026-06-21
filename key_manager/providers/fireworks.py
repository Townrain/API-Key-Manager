from .base import ProviderBase


class FireworksProvider(ProviderBase):
    name = "fireworks"
    base_url = "https://api.fireworks.ai"
    check_endpoint = "/inference/v1/models"
