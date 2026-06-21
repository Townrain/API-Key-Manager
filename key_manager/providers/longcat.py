from .base import ProviderBase


class LongCatProvider(ProviderBase):
    name = "longcat"
    base_url = "https://api.longcat.chat/openai/v1"
    check_endpoint = "/models"
