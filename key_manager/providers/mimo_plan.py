from .base import ProviderBase


class MiMoPlanProvider(ProviderBase):
    """MiMo Token Plan provider - uses different base URL for plan-based keys."""
    name = "mimo-plan"
    base_url = "https://token-plan-cn.xiaomimimo.com/v1"
    check_endpoint = "/models"
