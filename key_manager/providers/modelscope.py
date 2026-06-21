"""ModelScope provider - Chinese AI model platform."""
from .base import ProviderBase


class ModelScopeProvider(ProviderBase):
    name = "modelscope"
    base_url = "https://api-inference.modelscope.cn/v1"
    check_endpoint = "/models"

    async def get_models(self, client, key: str) -> list[str]:
        """Get models from ModelScope API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(f"{self.get_base_url()}/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    return [m["id"] for m in data["data"] if "id" in m]
            return []
        except Exception:
            return []
