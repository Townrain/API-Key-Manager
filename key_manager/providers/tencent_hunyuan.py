from .base import ProviderBase


class TencentHunyuanProvider(ProviderBase):
    """腾讯混元 provider - OpenAI compatible endpoint."""
    name = "tencent-hunyuan"
    base_url = "https://api.hunyuan.cloud.tencent.com/v1"
    check_endpoint = "/models"
