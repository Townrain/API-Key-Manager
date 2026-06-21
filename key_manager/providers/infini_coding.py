from .base import ProviderBase


class InfiniCodingProvider(ProviderBase):
    """无问芯穹 Coding Plan provider."""
    name = "infini-coding"
    base_url = "https://cloud.infini-ai.com/maas/coding/v1"
    check_endpoint = "/models"
