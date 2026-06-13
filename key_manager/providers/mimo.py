import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult


class MiMoProvider(ProviderBase):
    name = "mimo"
    base_url = "https://api.xiaomimimo.com/v1"
    check_endpoint = "/models"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def get_models(self, client, key: str) -> list[str]:
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    return [m["id"] for m in data["data"] if "id" in m]
            return []
        except Exception:
            return []

    async def test_token_limit(self, client, key: str, token_steps: list[int]) -> TestResult:
        headers = self.build_headers(key)
        last_success = None
        for step in token_steps:
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/chat/completions",
                    headers=headers,
                    json={
                        "model": "mimo-v1",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": step
                    }
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
