from .base import ProviderBase


class DMXAPIProvider(ProviderBase):
    name = "dmxapi"
    base_url = "https://www.dmxapi.cn/v1"
    check_endpoint = "/models"
