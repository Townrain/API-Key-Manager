from .base import ProviderBase


class DashScopeCodingProvider(ProviderBase):
    """阿里百炼 Coding Plan provider."""
    name = "dashscope-coding"
    base_url = "https://coding-intl.dashscope.aliyuncs.com/compatible-mode/v1"
    check_endpoint = "/models"
