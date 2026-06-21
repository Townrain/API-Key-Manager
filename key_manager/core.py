"""High-level facade for programmatic usage."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from key_manager.config import load_config
from key_manager.storage import KeyStore
from key_manager.providers import PROVIDERS, get_display_name
from key_manager.detector import detect_provider


class KeyManager:
    """Convenient facade for managing API keys programmatically.
    
    Usage:
        km = KeyManager()
        km.import_keys("keys.json")
        results = km.check(provider="openai")
        km.save()
    """
    
    def __init__(
        self, 
        config_path: str = "config.yaml", 
        config: dict[str, Any] | None = None
    ):
        """Initialize KeyManager.
        
        Args:
            config_path: Path to config.yaml file
            config: Direct config dict (overrides config_path)
        """
        self.config = config or load_config(config_path)
        self._store = KeyStore(
            self.config["storage"]["keys_file"], 
            self.config
        )
    
    @property
    def providers(self) -> dict[str, Any]:
        """Available provider registry."""
        return PROVIDERS
    
    def list_providers(self) -> list[str]:
        """List available provider names."""
        return list(PROVIDERS.keys())
    
    def get_provider(self, name: str):
        """Get a provider by name."""
        return PROVIDERS.get(name)
    
    def get_provider_display_name(self, name: str) -> str:
        """Get human-readable display name for a provider."""
        return get_display_name(name)
    
    def load_keys(self) -> dict[str, Any]:
        """Load keys from encrypted storage."""
        return self._store.load()
    
    def save_keys(self, data: dict[str, Any]) -> None:
        """Save keys to encrypted storage."""
        self._store.save(data)
    
    async def detect_provider(self, key: str) -> list[str]:
        """Auto-detect provider from key prefix."""
        import httpx
        from key_manager.detector import detect_provider as _detect_provider
        
        timeout = self.config.get("check", {}).get("timeout_seconds", 30)
        proxy = self.config.get("proxy") or None
        async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
            result = await _detect_provider(client, key)
            return [result] if result else []
    def list_keys(
        self, 
        provider: str | None = None,
        status: str | None = None
    ) -> dict[str, Any]:
        """List keys with optional filtering.
        
        Args:
            provider: Filter by provider name
            status: Filter by status (valid/invalid/error)
            
        Returns:
            Dict with keys matching filters
        """
        data = self.load_keys()
        result = {}
        
        for key, info in data.get("keys", {}).items():
            if provider and info.get("provider", "").lower() != provider.lower():
                continue
            if status and info.get("status") != status:
                continue
            result[key] = info
        
        return result
    
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about stored keys.
        
        Returns:
            Dict with provider counts and status breakdown
        """
        data = self.load_keys()
        stats: dict[str, Any] = {
            "total": 0,
            "by_provider": {},
            "by_status": {"valid": 0, "invalid": 0, "error": 0, "unknown": 0}
        }
        
        for key, info in data.get("keys", {}).items():
            stats["total"] += 1
            provider = info.get("provider", "unknown")
            status = info.get("status", "unknown")
            
            if provider not in stats["by_provider"]:
                stats["by_provider"][provider] = 0
            stats["by_provider"][provider] += 1
            
            if status in stats["by_status"]:
                stats["by_status"][status] += 1
        
        return stats
    
    async def check_key(
        self, 
        key: str, 
        provider: str | None = None,
        timeout: int = 30
    ) -> dict[str, Any]:
        """Check a single key.
        
        Args:
            key: API key to check
            provider: Provider name (auto-detected if not specified)
            timeout: Request timeout in seconds
            
        Returns:
            Dict with check results
        """
        import httpx
        from key_manager.providers import PROVIDERS
        
        if not provider:
            providers = await self.detect_provider(key)
            if not providers:
                return {"valid": False, "error": "Could not detect provider"}
            provider = providers[0]
        
        provider_obj = PROVIDERS.get(provider)
        if not provider_obj:
            return {"valid": False, "error": f"Unknown provider: {provider}"}
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            result = await provider_obj.check(client, key)
            return {
                "valid": result.valid,
                "provider": provider,
                "status_code": result.status_code,
                "latency_ms": result.latency_ms,
                "error": result.error
            }
    
    async def check_all(
        self,
        provider: str | None = None,
        status: str | None = None,
        concurrency: int = 100,
        timeout: int = 30
    ) -> dict[str, Any]:
        """Check all keys in storage.
        
        Args:
            provider: Filter by provider
            status: Filter by status
            concurrency: Max concurrent checks
            timeout: Request timeout
            
        Returns:
            Dict with check results
        """
        from key_manager.checker import run_check
        
        return await run_check(
            keys_file=self.config["storage"]["keys_file"],
            results_file=self.config["storage"]["check_results_file"],
            logs_dir=self.config["storage"]["logs_dir"],
            concurrency=concurrency,
            timeout=timeout,
            proxy=self.config.get("proxy") or None,
            retry_failed=self.config["check"]["retry_failed"],
            retry_count=self.config["check"]["retry_count"]
        )
    
    async def validate_keys(
        self,
        provider: str | None = None,
        status: str | None = None,
        concurrency: int = 100,
        timeout: int = 30
    ) -> dict[str, Any]:
        """Validate all keys (alias for check_all)."""
        return await self.check_all(
            provider=provider,
            status=status,
            concurrency=concurrency,
            timeout=timeout
        )
