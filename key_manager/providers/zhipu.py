from .base import ProviderBase, BalanceResult


class ZhipuProvider(ProviderBase):
    name = "zhipu"
    base_url = "https://open.bigmodel.cn/api/paas/v4"
    check_endpoint = "/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get quota/usage info via Zhipu monitoring API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    limits = data.get("data", {}).get("limits", [])
                    # Extract percentage used from limits
                    for limit in limits:
                        if limit.get("type") == "TOKENS_LIMIT":
                            percentage = limit.get("percentage", 0)
                            return BalanceResult(
                                supported=True,
                                balance=float(100 - percentage),  # remaining percentage
                                currency="%",
                                raw=data,
                            )
                return BalanceResult(supported=True, balance=None, raw=data)
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
