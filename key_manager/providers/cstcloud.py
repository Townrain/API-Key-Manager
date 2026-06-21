from .base import ProviderBase


class CSTCloudProvider(ProviderBase):
    """中国科技云 AI provider."""
    name = "cstcloud"
    base_url = "https://uni-api.cstcloud.cn/v1"
    check_endpoint = "/models"
