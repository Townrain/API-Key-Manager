from .base import ProviderBase


class HyperbolicProvider(ProviderBase):
    name = "hyperbolic"
    base_url = "https://api.hyperbolic.xyz/v1"
    check_endpoint = "/models"
