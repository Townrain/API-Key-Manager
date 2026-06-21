from .base import ProviderBase, BalanceResult


class OpenRouterProvider(ProviderBase):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    check_endpoint = "/auth/key"

    async def get_balance(self, client, key: str) -> BalanceResult:
        headers = self.build_headers(key)
        try:
            resp = await client.get(f"{self.get_base_url()}/auth/key", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                remaining = data.get("limit_remaining")
                if remaining is not None:
                    return BalanceResult(
                        supported=True,
                        balance=float(remaining),
                        currency="USD",
                        raw=data,
                    )
                return BalanceResult(supported=False, error="no limit_remaining in response")
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=False, error="invalid key")
            else:
                return BalanceResult(supported=False, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=False, error=str(e))
