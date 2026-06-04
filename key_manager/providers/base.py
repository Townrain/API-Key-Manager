from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from key_manager.url_override import custom_base_url

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


def simplify_error(error_msg: str, status_code: int = None) -> str:
    """Simplify error message for better readability."""
    if not error_msg:
        return ""
    
    # Common error patterns -> friendly messages
    error_lower = error_msg.lower()
    
    # Status code based
    if status_code == 401 or status_code == 403:
        return "Key 无效或无权限"
    elif status_code == 400:
        # 400 can mean various things, check error message
        pass  # Fall through to pattern matching
    elif status_code == 402:
        return "余额不足"
    elif status_code == 429:
        return "请求过于频繁，请稍后重试"
    elif status_code and status_code >= 500:
        return "服务商内部错误"
    
    # Pattern matching for common errors
    if "invalid" in error_lower and ("key" in error_lower or "token" in error_lower or "api" in error_lower):
        return "Key 无效"
    elif "authentication" in error_lower or "unauthorized" in error_lower:
        return "认证失败"
    elif "expired" in error_lower:
        return "Key 已过期"
    elif "rate limit" in error_lower or "too many" in error_lower:
        return "请求过于频繁"
    elif "insufficient" in error_lower or "balance" in error_lower or "overdue" in error_lower or "payment" in error_lower:
        return "余额不足"
    elif "suspended" in error_lower or "banned" in error_lower:
        return "账号被封禁"
    elif "forbidden" in error_lower or "permission" in error_lower or "access denied" in error_lower:
        return "无权限访问"
    elif "not found" in error_lower or "does not exist" in error_lower:
        return "模型不存在"
    elif "timeout" in error_lower:
        return "请求超时"
    elif "connection" in error_lower:
        return "连接失败"
    
    # If message is too long, truncate
    if len(error_msg) > 100:
        return error_msg[:100] + "..."
    
    return error_msg


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

    @property
    def check_model(self) -> str:
        """Model to use for probe/check. Override in subclass if needed."""
        return "gpt-3.5-turbo"  # Default model

    @abstractmethod
    def build_headers(self, key: str) -> dict:
        ...

    async def check(self, client, key: str) -> CheckResult:
        """Check key validity using multiple models from PROVIDER_MODELS.
        
        Strategy:
        1. Get models from PROVIDER_MODELS (Cherry Studio sync)
        2. Try first 5 models with /chat/completions
        3. If any succeeds, return valid
        4. If all fail, return last error
        
        Providers with non-standard APIs (Anthropic, Google, etc.) should override this.
        """
        import time
        from .models_registry import PROVIDER_MODELS
        
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        
        # Get models for this provider from Cherry Studio sync
        models = PROVIDER_MODELS.get(self.name, [])
        if not models:
            # Fallback to check_model if no models in registry
            models = [self.check_model]
        
        # Try first 5 models
        test_models = models[:5]
        last_error = ""
        last_status = None
        
        for model in test_models:
            start = time.monotonic()
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
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
                        last_error = data.get("error", {}).get("message", f"status {resp.status_code}")
                    except:
                        last_error = f"status {resp.status_code}"
                    last_status = resp.status_code
                
                # Simplify error for readability
                last_error = simplify_error(last_error, resp.status_code)
            except Exception as e:
                last_error = str(e)
                last_status = None
        
        # All models failed
        # All models failed
        return CheckResult(False, last_status, 0, last_error or "all models failed")
    @abstractmethod
    async def test_token_limit(self, client, key: str,
                                token_steps: list[int]) -> TestResult:
        ...

    @abstractmethod
    async def test_concurrency(self, client, key: str,
                                concurrency_steps: list[int]) -> TestResult:
        ...

    async def probe(self, client, key: str) -> CheckResult:
        """Probe for provider detection.
        
        Strategy:
        1. Get models from PROVIDER_MODELS (Cherry Studio sync)
        2. Try first 5 models with /chat/completions
        3. If any succeeds, return valid
        4. If all fail, return last error body for signature matching
        """
        import time
        from .models_registry import PROVIDER_MODELS
        
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        
        # Get models for this provider from Cherry Studio sync
        models = PROVIDER_MODELS.get(self.name, [])
        if not models:
            # Fallback to check_model if no models in registry
            models = [self.check_model]
        
        # Try first 5 models
        test_models = models[:5]
        last_body = ""
        last_status = None
        
        for model in test_models:
            start = time.monotonic()
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                )
                latency = (time.monotonic() - start) * 1000
                body = resp.text[:500]
                last_body = body
                last_status = resp.status_code
                
                if resp.status_code == 200:
                    return CheckResult(True, 200, latency, None, response_body=body)
                elif resp.status_code in (401, 403):
                    return CheckResult(False, resp.status_code, latency, "invalid key", response_body=body)
                elif resp.status_code == 429:
                    return CheckResult(True, 429, latency, "rate limited", response_body=body)
                # For other errors, try next model
            except Exception as e:
                last_body = str(e)
                last_status = None
        
        # All models failed - return last error for signature matching
        latency = (time.monotonic() - start) * 1000 if test_models else 0
        return CheckResult(False, last_status, latency, f"all models failed", response_body=last_body)

    async def get_models(self, client, key: str) -> list[str]:
        """Get list of available models. Override in subclass for custom implementation."""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
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
        """Get account balance. Override in subclass for custom implementation."""
        return BalanceResult(supported=False)
