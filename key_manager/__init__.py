"""Key Manager - Batch API key management for 45+ AI providers."""
from key_manager.core import KeyManager
from key_manager.errors import ErrorCode, KeyManagerError
from key_manager.providers import PROVIDERS, get_display_name
from key_manager.storage import KeyStore

__all__ = [
    "KeyManager",
    "PROVIDERS",
    "get_display_name",
    "KeyManagerError",
    "ErrorCode",
    "KeyStore",
]

__version__ = "5.0.1"

