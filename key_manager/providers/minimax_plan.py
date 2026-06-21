from .base import ProviderBase


class MiniMaxTokenPlanProvider(ProviderBase):
    """MiniMax Token Plan provider - uses different base URL for plan-based keys."""
    name = "minimax-plan"
    base_url = "https://api.minimax.chat/v1"
    check_endpoint = "/models"
