from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.url_override import custom_base_url

ERROR_TYPES = {
    "invalid_key": "invalid_key",
    "rate_limited": "rate_limited",
    "insufficient_balance": "insufficient_balance",
    "quota_exceeded": "quota_exceeded",
    "account_suspended": "account_suspended",
    "forbidden": "forbidden",
    "not_found": "not_found",
    "server_error": "server_error",
    "timeout": "timeout",
    "connection_error": "connection_error",
    "unknown": "unknown",
}


@dataclass
class CheckResult:
    valid: bool
    status_code: Optional[int]
    latency_ms: float
    error: Optional[str]
    rate_limit_info: Optional[dict] = None
    error_type: Optional[str] = None
    response_body: Optional[str] = None


@dataclass
class TestResult:
    max_tokens: Optional[int] = None
    max_concurrency: Optional[int] = None
    rpm_limit: Optional[int] = None
    models: Optional[list[str]] = None
    error: Optional[str] = None


@dataclass
class BalanceResult:
    supported: bool
    balance: Optional[float] = None
    currency: str = "USD"
    raw: Optional[dict] = None
    error: Optional[str] = None


class ProviderBase(ABC):
    """Abstract base for all API providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        ...

    def get_base_url(self) -> str:
        """Return effective base URL, respecting per-request override."""
        override = custom_base_url.get(None)
        return override if override else self.base_url

    @property
    @abstractmethod
    def check_endpoint(self) -> str:
        ...

    @abstractmethod
    def build_headers(self, key: str) -> dict:
        ...

    @abstractmethod
    async def check(self, client, key: str) -> CheckResult:
        ...

    @abstractmethod
    async def test_token_limit(self, client, key: str,
                                token_steps: list[int]) -> TestResult:
        ...

    @abstractmethod
    async def test_concurrency(self, client, key: str,
                                concurrency_steps: list[int]) -> TestResult:
        ...

    async def probe(self, client, key: str) -> CheckResult:
        """Lightweight probe for provider detection. Uses GET to check_endpoint."""
        import time
        headers = self.build_headers(key)
        start = time.monotonic()
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
                headers=headers
            )
            latency = (time.monotonic() - start) * 1000
            body = resp.text[:500]  # Capture truncated body for signature matching
            if resp.status_code == 200:
                return CheckResult(True, 200, latency, None, response_body=body)
            elif resp.status_code in (401, 403):
                return CheckResult(False, resp.status_code, latency, "invalid key", response_body=body)
            elif resp.status_code == 429:
                return CheckResult(True, 429, latency, "rate limited", response_body=body)
            else:
                return CheckResult(False, resp.status_code, latency, f"status {resp.status_code}", response_body=body)
        except Exception as e:
            return CheckResult(False, None, (time.monotonic() - start) * 1000, str(e))

    async def get_models(self, client, key: str) -> list[str]:
        """Get list of available models. Override in subclass for custom implementation."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.base_url}{self.check_endpoint}",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                # Try to extract model IDs from response
                if isinstance(data, dict):
                    if "data" in data:
                        return [m.get("id", "") for m in data["data"] if m.get("id")]
                    elif "models" in data:
                        return [m.get("name", "") for m in data["models"] if m.get("name")]
                elif isinstance(data, list):
                    return [m.get("id", m.get("name", "")) for m in data if isinstance(m, dict)]
            return []
        except Exception:
            return []

    async def test_concurrency_for_model(self, client, key: str, model: str, concurrency_steps: list[int]) -> TestResult:
        """Test concurrency for a specific model using chat completions. Override in subclass for custom implementation."""
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
        """Probe a specific model with a minimal chat completion request. Override in subclass for custom implementation."""
        try:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
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
        """Get account balance. Override in subclass for custom implementation."""
        return BalanceResult(supported=False)
