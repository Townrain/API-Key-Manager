from .base import BalanceResult, ProviderBase


class SiliconFlowProvider(ProviderBase):
    name = "siliconflow"
    base_url = "https://api.siliconflow.cn/v1"
    check_endpoint = "/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get account balance via SiliconFlow user info API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}/user/info",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                user_data = data.get("data", {})
                return BalanceResult(
                    supported=True,
                    balance=float(user_data.get("balance", 0)),
                    currency="CNY",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
