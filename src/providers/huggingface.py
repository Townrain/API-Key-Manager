import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult


class HuggingFaceProvider(ProviderBase):
    name = "huggingface"
    base_url = "https://huggingface.co"
    check_endpoint = "/api/whoami-v2"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def get_models(self, client, key: str) -> list[str]:
        return []

    async def check(self, client, key: str) -> CheckResult:
        headers = self.build_headers(key)
        start = time.monotonic()
        try:
            resp = await client.get(f"{self.get_base_url()}{self.check_endpoint}", headers=headers)
            latency = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                return CheckResult(True, 200, latency, None)
            elif resp.status_code in (401, 403):
                return CheckResult(False, resp.status_code, latency, "invalid key")
            elif resp.status_code == 429:
                return CheckResult(True, 429, latency, "rate limited")
            else:
                return CheckResult(False, resp.status_code, latency, f"status {resp.status_code}")
        except Exception as e:
            return CheckResult(False, None, (time.monotonic() - start) * 1000, str(e))

    async def test_token_limit(self, client, key: str, token_steps: list[int]) -> TestResult:
        return TestResult(max_tokens=None)

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
