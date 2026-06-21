from .base import ProviderBase


class MiniMaxProvider(ProviderBase):
    name = "minimax"
    base_url = "https://api.minimax.chat/v1"
    check_endpoint = "/models"
