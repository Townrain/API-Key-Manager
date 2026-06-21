from .base import ProviderBase, BalanceResult


class KimiProvider(ProviderBase):
    name = "kimi"
    base_url = "https://api.moonshot.cn/v1"
    check_endpoint = "/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get account balance via Kimi balance API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}/users/me/balance",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                balance_data = data.get("data", {})
                return BalanceResult(
                    supported=True,
                    balance=float(balance_data.get("available_balance", 0)),
                    currency="CNY",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
