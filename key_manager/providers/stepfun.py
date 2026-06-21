from .base import BalanceResult, ProviderBase


class StepFunProvider(ProviderBase):
    name = "stepfun"
    base_url = "https://api.stepfun.com/v1"
    check_endpoint = "/models"

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get account balance via StepFun accounts API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                "https://api.stepfun.com/v1/accounts",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                return BalanceResult(
                    supported=True,
                    balance=float(data.get("balance", 0)),
                    currency="CNY",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
