from .base import ProviderBase


class OCoolAIProvider(ProviderBase):
    name = "ocoolai"
    base_url = "https://api.ocoolai.com/v1"
    check_endpoint = "/models"
