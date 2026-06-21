from .base import ProviderBase


class ZhipuCodingProvider(ProviderBase):
    """智谱 GLM Coding Plan provider."""
    name = "zhipu-coding"
    base_url = "https://open.bigmodel.cn/api/coding/paas/v4"
    check_endpoint = "/models"
