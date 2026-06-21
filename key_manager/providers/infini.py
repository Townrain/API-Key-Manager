from .base import ProviderBase, BalanceResult


class InfiniProvider(ProviderBase):
    name = "infini"
    base_url = "https://cloud.infini-ai.com/maas/v1"
    check_endpoint = "/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get usage info via Infini coding usage API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                "https://cloud.infini-ai.com/maas/coding/usage",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                # Extract remaining quota from 30_day window
                usage = data.get("30_day", {})
                remain = usage.get("remain", 0)
                return BalanceResult(
                    supported=True,
                    balance=float(remain),
                    currency="tokens",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
