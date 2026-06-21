from .base import ProviderBase


class NvidiaProvider(ProviderBase):
    name = "nvidia"
    base_url = "https://integrate.api.nvidia.com/v1"
    check_endpoint = "/models"
