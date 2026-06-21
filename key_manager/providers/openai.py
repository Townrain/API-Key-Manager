import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult


class OpenAIProvider(ProviderBase):
    name = "openai"
    base_url = "https://api.openai.com"
    check_endpoint = "/v1/models"





    async def check_real(self, client, key: str) -> CheckResult:
        return await self.check(client, key)
    async def test_concurrency(self, client, key: str,
                                concurrency_steps: list[int]) -> TestResult:
        headers = self.build_headers(key)
        last_success = None
        rpm_limit = None

        for step in concurrency_steps:
            tasks = []
            for _ in range(step):
                tasks.append(self._concurrency_probe(client, headers))
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success = sum(1 for r in results if not isinstance(r, Exception) and r)
            rate_limited = sum(1 for r in results if not isinstance(r, Exception) and not r)

            if rate_limited / step >= 0.3:
                break
            last_success = step

        return TestResult(max_concurrency=last_success, rpm_limit=rpm_limit)

    async def _concurrency_probe(self, client, headers: dict) -> bool:
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
                headers=headers
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _extract_rate_limit(self, headers) -> dict:
        info = {}
        if "x-ratelimit-remaining-requests" in headers:
            info["remaining"] = int(headers["x-ratelimit-remaining-requests"])
        if "x-ratelimit-limit-requests" in headers:
            info["limit"] = headers["x-ratelimit-limit-requests"]
        if "x-ratelimit-reset-requests" in headers:
            info["reset"] = headers["x-ratelimit-reset-requests"]
        return info if info else None
