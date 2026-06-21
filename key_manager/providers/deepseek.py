import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult, BalanceResult


class DeepSeekProvider(ProviderBase):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
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
        """Test max token output by sending a large value and parsing error response.
        
        Strategy: Send 1000000 tokens, parse error to get actual limit.
        """
        import re
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        
        large_tokens = 1000000
        
        try:
            resp = await client.post(
                f"{self.get_base_url()}/chat/completions",
                headers=headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": large_tokens
                }
            )
            
            if resp.status_code == 200:
                return TestResult(max_tokens=large_tokens)
            
            # Parse error to extract limit
            try:
                error_data = resp.json()
                error_msg = error_data.get("error", {}).get("message", "")
                
                # Try to find limit after 'maximum' or 'max' keyword
                max_match = re.search(r'(?:maximum|max)\s+(?:is\s+)?(\d+)', error_msg, re.IGNORECASE)
                if max_match:
                    limit = int(max_match.group(1))
                    if limit >= 100:
                        return TestResult(max_tokens=limit)
                
                # Fallback: find numbers and use the second largest
                numbers = re.findall(r'\d+', error_msg)
                if len(numbers) >= 2:
                    sorted_nums = sorted(set(int(n) for n in numbers), reverse=True)
                    for num in sorted_nums:
                        if num >= 100:
                            return TestResult(max_tokens=num)
                elif numbers:
                    num = int(numbers[0])
                    if num >= 100:
                        return TestResult(max_tokens=num)
            except Exception:
                pass
            
            return TestResult(max_tokens=None, error="Could not parse token limit")
        except Exception as e:
            return TestResult(max_tokens=None, error=str(e))


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

    async def test_concurrency_for_model(self, client, key: str, model: str, concurrency_steps: list[int]) -> TestResult:
        """Test concurrency for a specific model using chat completions."""
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        last_success = None
        for step in concurrency_steps:
            tasks = [self._probe_model(client, headers, model) for _ in range(step)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            rate_limited = sum(1 for r in results if not isinstance(r, Exception) and not r)
            if rate_limited / step >= 0.3:
                break
            last_success = step
        return TestResult(max_concurrency=last_success)

    async def _probe_model(self, client, headers, model: str) -> bool:
        """Probe a specific model with a minimal chat completion request."""
        try:
            resp = await client.post(
                f"{self.get_base_url()}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def get_balance(self, client, key: str) -> BalanceResult:
        """Get account balance via DeepSeek balance API."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}/user/balance",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                balance_infos = data.get("balance_infos", [])
                if balance_infos:
                    info = balance_infos[0]
                    return BalanceResult(
                        supported=True,
                        balance=float(info.get("total_balance", 0)),
                        currency=info.get("currency", "USD"),
                        raw=data,
                    )
                return BalanceResult(supported=True, balance=0.0, raw=data)
            elif resp.status_code in (401, 403):
                return BalanceResult(supported=True, error="invalid key or forbidden")
            else:
                return BalanceResult(supported=True, error=f"status {resp.status_code}")
        except Exception as e:
            return BalanceResult(supported=True, error=str(e))
