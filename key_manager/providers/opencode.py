"""OpenCode Go provider - low-cost subscription service for open-source models."""
import asyncio

from .base import ProviderBase, TestResult


class OpenCodeGoProvider(ProviderBase):
    name = "opencode-go"
    base_url = "https://opencode.ai/zen/go"
    check_endpoint = "/v1/models"

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

    async def test_token_limit(self, client, key: str,
                                token_steps: list[int]) -> TestResult:
        """Test max token output by finding an available model from API."""
        headers = self.build_headers(key)
        models = await self.get_models(client, key)
        if not models:
            return TestResult(error="no available models found")

        # Find first working model
        for model_id in models:
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/v1/chat/completions",
                    headers=headers,
                    json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
                    timeout=10
                )
                if resp.status_code != 200:
                    continue

                # Model works, test token limit
                last_success = None
                for step in token_steps:
                    try:
                        resp = await client.post(
                            f"{self.get_base_url()}/v1/chat/completions",
                            headers=headers,
                            json={"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": step}
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

                if last_success:
                    return TestResult(max_tokens=last_success)
            except Exception:
                continue

        return TestResult(error="all models failed")

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

            sum(1 for r in results if not isinstance(r, Exception) and r)
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
