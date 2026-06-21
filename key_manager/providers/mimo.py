from .base import ProviderBase


class MiMoProvider(ProviderBase):
    name = "mimo"
    base_url = "https://api.xiaomimimo.com/v1"
    check_endpoint = "/models"
