import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult


class GoogleProvider(ProviderBase):
    name = "google"
    base_url = "https://generativelanguage.googleapis.com"
    check_endpoint = "/v1beta/models"

    def build_headers(self, key: str) -> dict:
        return {}

    async def get_models(self, client, key: str) -> list[str]:
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}?key={key}"
            )
            if resp.status_code == 200:
                data = resp.json()
                if "models" in data:
                    return [m["name"].split("/")[-1] for m in data["models"] if "name" in m]
            return []
        except Exception:
            return []

    async def check(self, client, key: str) -> CheckResult:
        """Real usage test - try to make a minimal chat completion request."""
        start = time.monotonic()
        try:
            resp = await client.post(
                f"{self.get_base_url()}/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                json={
                    "contents": [{"parts": [{"text": "hi"}]}],
                    "generationConfig": {"maxOutputTokens": 5}
                }
            )
            latency = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                return CheckResult(True, 200, latency, None)
            elif resp.status_code in (400, 403):
                return CheckResult(False, resp.status_code, latency, "invalid key or forbidden")
            elif resp.status_code == 429:
                return CheckResult(False, 429, latency, "rate limited")
            else:
                try:
                    data = resp.json()
                    error_msg = data.get("error", {}).get("message", f"status {resp.status_code}")
                except Exception:
                    error_msg = f"status {resp.status_code}"
                return CheckResult(False, resp.status_code, latency, error_msg)
        except Exception as e:
            return CheckResult(False, None, (time.monotonic() - start) * 1000, str(e))

    async def test_token_limit(self, client, key: str, token_steps: list[int]) -> TestResult:
        last_success = None
        for step in token_steps:
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                    json={
                        "contents": [{"parts": [{"text": "hi"}]}],
                        "generationConfig": {"maxOutputTokens": step}
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
        last_success = None
        for step in concurrency_steps:
            tasks = [self._probe(client, key) for _ in range(step)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            rate_limited = sum(1 for r in results if not isinstance(r, Exception) and not r)
            if rate_limited / step >= 0.3:
                break
            last_success = step
        return TestResult(max_concurrency=last_success)

    async def _probe(self, client, key) -> bool:
        try:
            resp = await client.get(f"{self.get_base_url()}{self.check_endpoint}?key={key}")
            return resp.status_code == 200
        except Exception:
            return False
