"""Shared test helpers and fixtures for API Key Manager tests.

This module provides reusable test infrastructure to reduce duplication
across test files.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from key_manager.providers.base import ProviderBase, CheckResult, TestResult


# ── MockProvider Classes ─────────────────────────────────────────────────────

class MockProvider(ProviderBase):
    """Simple mock provider for testing base check logic.
    
    Usage:
        provider = MockProvider()
        result = await provider.check(client, "test-key")
    """
    name = "test-provider"
    base_url = "https://api.test.com/v1"
    check_endpoint = "/models"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def test_token_limit(self, client, key, token_steps):
        pass

    async def test_concurrency(self, client, key, concurrency_steps):
        pass


class MockProviderWithTokenLimit(MockProvider):
    """Mock provider with configurable token limit testing.
    
    Usage:
        provider = MockProviderWithTokenLimit(max_tokens=16384)
        result = await provider.test_token_limit(client, "key")
    """
    
    async def test_token_limit(self, client, key, models=None):
        """Return configured max_tokens."""
        return TestResult(max_tokens=16384, error=None)

    async def test_concurrency(self, client, key, models=None):
        """Return configured max_concurrency."""
        return TestResult(max_concurrency=10, error=None)


# ── Mock Provider Factory ────────────────────────────────────────────────────

def make_mock_provider(
    name: str = "openai",
    check_valid: bool = True,
    models: list[str] | None = None,
    balance: float = 100.0,
    include_probe: bool = False,
) -> MagicMock:
    """Create a mock provider with configurable behavior.
    
    Args:
        name: Provider name
        check_valid: Whether check() returns valid=True
        models: Model list for get_models()
        balance: Balance amount for get_balance()
        include_probe: Whether to include probe and _probe_model mocks
        
    Returns:
        MagicMock provider instance
        
    Usage:
        provider = make_mock_provider("openai", check_valid=False)
        result = await provider.check(client, "key")
    """
    provider = MagicMock()
    provider.name = name
    provider.base_url = f"https://api.{name}.com"
    provider.check_endpoint = "/v1/models" if name == "openai" else "/models"
    provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
    provider.get_base_url.return_value = provider.base_url
    
    provider.check = AsyncMock(return_value=SimpleNamespace(
        valid=check_valid,
        status_code=200 if check_valid else 401,
        latency_ms=100.0,
        error=None if check_valid else "invalid key",
        error_type=None if check_valid else "invalid_key",
        response_body=None,
    ))
    
    provider.get_models = AsyncMock(return_value=models or ["gpt-3.5-turbo", "gpt-4"])
    
    provider.get_balance = AsyncMock(return_value=SimpleNamespace(
        supported=True,
        balance=balance,
        currency="USD",
        error=None,
    ))
    
    if include_probe:
        provider.probe = AsyncMock(return_value=SimpleNamespace(
            valid=True,
            status_code=200,
            latency_ms=50.0,
            error=None,
            response_body='{"data": []}',
        ))
        provider._probe_model = AsyncMock(return_value=True)
    
    return provider


# ── Key Data Helpers ─────────────────────────────────────────────────────────

def make_key_info(
    key: str,
    provider: str = "openai",
    status: str = "unknown",
    **kwargs,
) -> dict:
    """Create a single key info dict.
    
    Args:
        key: The API key string
        provider: Provider name
        status: Key status (unknown, valid, invalid, error)
        **kwargs: Additional fields to merge
        
    Returns:
        dict with key info structure
        
    Usage:
        info = make_key_info("sk-test123", "openai", "valid")
    """
    info = {
        "key": key,
        "key_masked": f"{key[:6]}...{key[-4:]}",
        "provider": provider,
        "status": status,
        "last_checked": None,
        "checks": [],
        "tests": {},
        "sources": [{"file": "test.json", "batch": "test"}],
    }
    info.update(kwargs)
    return info


def make_keys_data_from_dict(keys: dict) -> dict:
    """Build keys.json structure from a dict of key_info dicts.
    
    Args:
        keys: Dict mapping key strings to key_info dicts
        
    Returns:
        dict with keys.json structure
        
    Usage:
        data = make_keys_data_from_dict({
            "sk-test123": make_key_info("sk-test123", "openai", "valid")
        })
    """
    return {
        "keys": keys,
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "last_updated": "2024-01-01T00:00:00Z",
        },
    }


def make_keys_data_from_list(
    keys: list[dict] | None = None,
) -> dict:
    """Build keys.json structure from a list of key specs.
    
    Args:
        keys: List of dicts with key, provider, status fields.
              If None, creates a single default openai key.
              
    Returns:
        dict with keys.json structure
        
    Usage:
        data = make_keys_data_from_list([
            {"key": "sk-test123", "provider": "openai", "status": "valid"},
            {"key": "sk-test456", "provider": "anthropic", "status": "unknown"},
        ])
    """
    if keys is None:
        keys = [{"key": "sk-test123456789", "provider": "openai", "status": "unknown"}]
    
    keys_dict = {}
    for k in keys:
        key = k["key"]
        keys_dict[key] = make_key_info(
            key=key,
            provider=k["provider"],
            status=k.get("status", "unknown"),
            last_checked=k.get("last_checked"),
            checks=k.get("checks", []),
            tests=k.get("tests", {}),
            sources=k.get("sources", [{"file": "test.json", "batch": "test"}]),
        )
    
    return {
        "keys": keys_dict,
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "last_updated": "2024-01-01T00:00:00Z",
        },
    }


# ── Async Context Manager Mock ───────────────────────────────────────────────

class AsyncContextManagerMock:
    """Mock for async context managers (e.g., httpx.AsyncClient).
    
    Usage:
        mock_client = AsyncContextManagerMock()
        async with mock_client as client:
            response = await client.get("...")
    """
    
    def __init__(self, return_value=None):
        self.return_value = return_value or MagicMock()
        self.__aenter__ = AsyncMock(return_value=self.return_value)
        self.__aexit__ = AsyncMock(return_value=False)
