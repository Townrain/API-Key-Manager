from .base import ProviderBase, BalanceResult


class TogetherProvider(ProviderBase):
    name = "together"
    base_url = "https://api.together.xyz"
    check_endpoint = "/v1/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get organization info via Together API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}/v1/organizations/me",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                # Together API returns org info, not direct balance
                # Try to extract any balance-related fields
                return BalanceResult(
                    supported=True,
                    balance=None,
                    currency="USD",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
