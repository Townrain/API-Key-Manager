import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult, BalanceResult


class DashScopeProvider(ProviderBase):
    name = "dashscope"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    check_endpoint = "/models"
    check_model = "qwen-turbo"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def get_models(self, client, key: str) -> list[str]:
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

    async def check(self, client, key: str) -> CheckResult:
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        start = time.monotonic()
        try:
            resp = await client.post(
                f"{self.get_base_url()}/chat/completions",
                headers=headers,
                json={"model": "qwen-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
            )
            latency = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return CheckResult(True, 200, latency, None)
            elif resp.status_code in (401, 403):
                return CheckResult(False, resp.status_code, latency, "invalid key or forbidden")
            elif resp.status_code == 429:
                return CheckResult(False, 429, latency, "rate limited")
            else:
                try:
                    data = resp.json()
                    error_msg = data.get("error", {}).get("message", f"status {resp.status_code}")
                except:
                    error_msg = f"status {resp.status_code}"
                return CheckResult(False, resp.status_code, latency, error_msg)
        except Exception as e:
            return CheckResult(False, None, (time.monotonic() - start) * 1000, str(e))

    async def test_token_limit(self, client, key: str, token_steps: list[int]) -> TestResult:
        headers = self.build_headers(key)
        last_success = None
        for step in token_steps:
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/chat/completions",
                    headers=headers,
                    json={"model": "qwen-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": step}
                )
                if resp.status_code == 200:
                    last_success = step
                elif resp.status_code in (400, 413):
                    break
                elif resp.status_code == 429:
                    await asyncio.sleep(1)
                    continue
                else:
                    break
            except Exception:
                break
        return TestResult(max_tokens=last_success)


    async def check_real(self, client, key: str) -> CheckResult:
        return await self.check(client, key)
    async def test_concurrency(self, client, key: str, concurrency_steps: list[int]) -> TestResult:
        headers = self.build_headers(key)
        last_success = None
        for step in concurrency_steps:
            tasks = [self._probe(client, headers) for _ in range(step)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            rate_limited = sum(1 for r in results if not isinstance(r, Exception) and not r)
            if rate_limited / step >= 0.3:
                break
            last_success = step
        return TestResult(max_concurrency=last_success)

    async def _probe(self, client, headers) -> bool:
        try:
            resp = await client.get(f"{self.get_base_url()}{self.check_endpoint}", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get account balance via DashScope recharge balance API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"https://dashscope.aliyuncs.com/api/v1/recharge/recharge-balance/query",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                return BalanceResult(
                    supported=True,
                    balance=float(data.get("available_balance", 0)),
                    currency="CNY",
                    raw=data,
                )
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
