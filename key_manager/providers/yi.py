from .base import ProviderBase


class YiProvider(ProviderBase):
    name = "yi"
    base_url = "https://api.lingyiwanwu.com/v1"
    check_endpoint = "/models"
