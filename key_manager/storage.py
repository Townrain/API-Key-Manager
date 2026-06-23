import base64
import json
import logging
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from key_manager.errors import ErrorCode, StorageError

logger = logging.getLogger(__name__)


_ITERATIONS = 600_000  # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
_LEGACY_SALT = b"key-manager-aes256gcm-salt-v1"  # For backward compatibility
_API_TOKEN_SALT = b"key-manager-api-auth-token-v1"  # Domain-specific salt for API token
_SALT_LEN = 16
_NONCE_LEN = 12

# Key cache: (passphrase, salt) -> derived key
_key_cache: dict[tuple[str, bytes], bytes] = {}


def _derive_key(passphrase: str, salt: bytes = None, cache: bool = True) -> bytes:
    if salt is None:
        salt = _LEGACY_SALT
    if cache:
        cache_key = (passphrase, salt)
        if cache_key in _key_cache:
            return _key_cache[cache_key]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    key = kdf.derive(passphrase.encode("utf-8"))
    if cache:
        _key_cache[cache_key] = key
    return key

def clear_key_cache() -> None:
    """Clear the derived-key cache.
    
    Call this after changing the encryption passphrase to avoid
    returning stale cached keys.
    """
    _key_cache.clear()


def derive_api_token(config: dict | None = None, salt: bytes = None) -> str:
    """Derive an API authentication token from the encryption passphrase.
    
    Uses a different salt than storage encryption to avoid cross-contamination.
    The derived token is cached for performance.
    
    Args:
        config: Optional config dict with encryption.passphrase.
        salt: Optional custom salt bytes. Defaults to built-in API token salt.
    """
    if salt is None:
        salt = _API_TOKEN_SALT
    passphrase = _get_passphrase(config)
    cache_key = (passphrase, salt)
    if cache_key in _key_cache:
        # Return cached token as hex string
        return _key_cache[cache_key].hex()
    
    # Derive a 32-byte token using PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    token_bytes = kdf.derive(passphrase.encode("utf-8"))
    _key_cache[cache_key] = token_bytes
    return token_bytes.hex()

def _get_passphrase(config: dict | None = None) -> str:
    """Get encryption passphrase from config, env var, or auto-generate."""
    # 1. Check environment variable
    secret = os.environ.get("KEY_MANAGER_SECRET")
    if secret:
        return secret

    # 2. Check config file
    if config and config.get("encryption", {}).get("passphrase"):
        return config["encryption"]["passphrase"]

    # 3. Auto-generate and save
    passphrase = secrets.token_urlsafe(32)
    _save_passphrase_to_config(passphrase)
    logger.info("Auto-generated encryption passphrase and saved to config.yaml")
    return passphrase


def _save_passphrase_to_config(passphrase: str) -> None:
    """Append encryption passphrase to config.yaml without rewriting existing content."""
    config_path = Path("config.yaml")

    try:
        existing = ""
        if config_path.exists():
            existing = config_path.read_text(encoding="utf-8")
            # Check if encryption section already exists
            if "encryption:" in existing and "passphrase:" in existing:
                logger.debug("Encryption passphrase already in config.yaml, skipping")
                return

        # Append encryption section
        encryption_block = (
            "\n# ---- Encryption ----\n"
            "# Auto-generated passphrase for AES-256-GCM encryption\n"
            "encryption:\n"
            f'  passphrase: "{passphrase}"\n'
        )
        with open(config_path, "a", encoding="utf-8") as f:
            f.write(encryption_block)
        logger.info(f"Saved encryption passphrase to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save passphrase to config.yaml: {e}")


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)




class KeyStore:

    def __init__(self, path: str | Path, config: dict | None = None):
        self.path = Path(path)
        self.config = config or {}

    def load(self) -> dict:
        if not self.path.exists():
            raise StorageError(code=ErrorCode.STORAGE_READ_ERROR, message=f"File not found: {self.path}")
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise StorageError(code=ErrorCode.STORAGE_READ_ERROR, message=f"Invalid JSON in {self.path}: {e}") from e
        if isinstance(data, dict) and data.get("encrypted") is True:
            return self._decrypt(data)
        return data

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.config.get("storage", {}).get("encrypted", True) is True
        if encrypted:
            payload = self._encrypt(data)
        else:
            payload = data
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            os.chmod(self.path, 0o600)
        except (OSError, AttributeError):
            pass

    def migrate(self) -> dict:
        data = self.load()
        self.save(data)
        return data

    def rotate_key(self, new_passphrase: str) -> dict:
        encrypted = self.config.get("storage", {}).get("encrypted", True) is True
        if not encrypted:
            logger.warning("rotate_key called but storage.encrypted=false — passphrase not used")
        clear_key_cache()  # Invalidate stale cached keys from old passphrase
        if not self.path.exists():
            raise StorageError(code=ErrorCode.STORAGE_READ_ERROR, message=f"File not found: {self.path}")
        raw = self.path.read_text(encoding="utf-8")
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as e:
            raise StorageError(code=ErrorCode.STORAGE_READ_ERROR, message=f"Invalid JSON in {self.path}: {e}") from e
        if isinstance(envelope, dict) and envelope.get("encrypted") is True:
            data = self._decrypt(envelope)
        else:
            data = envelope
        self.config.setdefault("encryption", {})["passphrase"] = new_passphrase
        os.environ["KEY_MANAGER_SECRET"] = new_passphrase
        self.save(data)
        return data

    def _encrypt(self, data: dict) -> dict:
        passphrase = _get_passphrase(self.config)
        salt = os.urandom(_SALT_LEN)  # Random salt per encryption
        key = _derive_key(passphrase, salt, cache=False)  # Don't cache random-salt keys
        nonce = os.urandom(_NONCE_LEN)
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        aes = AESGCM(key)
        ciphertext = aes.encrypt(nonce, plaintext, None)
        return {
            "encrypted": True,
            "salt": _b64e(salt),  # Store salt in envelope
            "nonce": _b64e(nonce),
            "data": _b64e(ciphertext),
        }

    def _decrypt(self, envelope: dict) -> dict:
        try:
            # Read salt from envelope, fall back to legacy
            salt = _b64d(envelope["salt"]) if "salt" in envelope else _LEGACY_SALT
            nonce = _b64d(envelope["nonce"])
            ciphertext = _b64d(envelope["data"])
        except (KeyError, ValueError) as e:
            raise StorageError(code=ErrorCode.STORAGE_ENCRYPTION_ERROR, message=f"Malformed encrypted envelope: {e}") from e
        passphrase = _get_passphrase(self.config)
        key = _derive_key(passphrase, salt)
        aes = AESGCM(key)
        try:
            plaintext = aes.decrypt(nonce, ciphertext, None)
        except Exception as e:
            raise StorageError(code=ErrorCode.STORAGE_ENCRYPTION_ERROR, message=f"Decryption failed (wrong key or tampered data): {e}") from e
        try:
            return json.loads(plaintext.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise StorageError(code=ErrorCode.STORAGE_ENCRYPTION_ERROR, message=f"Decrypted data is not valid JSON: {e}") from e
