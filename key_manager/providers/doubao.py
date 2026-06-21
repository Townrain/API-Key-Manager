from .base import ProviderBase


class DoubaoProvider(ProviderBase):
    name = "doubao"
    base_url = "https://ark.cn-beijing.volces.com/api/v3"
    check_endpoint = "/models"
