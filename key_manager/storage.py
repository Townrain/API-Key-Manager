import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from key_manager.errors import ErrorCode, StorageError


_ITERATIONS = 100_000
_LEGACY_SALT = b"key-manager-aes256gcm-salt-v1"  # For backward compatibility
_SALT_LEN = 16
_NONCE_LEN = 12


def _derive_key(passphrase: str, salt: bytes = None) -> bytes:
    if salt is None:
        salt = _LEGACY_SALT
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _get_passphrase(config: dict | None = None) -> str:
    secret = os.environ.get("KEY_MANAGER_SECRET")
    if secret:
        return secret
    if config and config.get("encryption", {}).get("passphrase"):
        return config["encryption"]["passphrase"]
    raise StorageError(
        code=ErrorCode.STORAGE_ENCRYPTION_ERROR,
        message="No passphrase found. Set KEY_MANAGER_SECRET env var or "
        "configure encryption.passphrase in config.yaml"
    )


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
        envelope = self._encrypt(data)
        self.path.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def migrate(self) -> dict:
        data = self.load()
        self.save(data)
        return data

    def rotate_key(self, new_passphrase: str) -> dict:
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
        key = _derive_key(passphrase, salt)
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
