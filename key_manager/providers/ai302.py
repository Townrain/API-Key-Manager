from .base import ProviderBase


class AI302Provider(ProviderBase):
    name = "ai302"
    base_url = "https://api.302.ai/v1"
    check_endpoint = "/models"
