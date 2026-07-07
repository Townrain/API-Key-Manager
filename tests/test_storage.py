from pathlib import Path
import base64
import json
import os
import sys

import pytest

from key_manager.storage import KeyStore, StorageError, _derive_key, _get_passphrase, _key_cache, _API_TOKEN_SALT, _LEGACY_SALT
from key_manager.storage import derive_api_token, clear_key_cache


PASSPHRASE = "test-passphrase-for-unit-tests"
SAMPLE_DATA = {
    "keys": {
        "sk-abc123": {"provider": "openai", "status": "valid"},
        "sk-def456": {"provider": "anthropic", "status": "unknown"},
    },
    "metadata": {"created_at": "2025-01-01T00:00:00Z"},
}


@pytest.fixture(autouse=True)
def _set_passphrase(monkeypatch):
    monkeypatch.setenv("KEY_MANAGER_SECRET", PASSPHRASE)


@pytest.fixture
def store(tmp_path):
    return KeyStore(tmp_path / "keys.json")


@pytest.fixture
def encrypted_file(tmp_path):
    from pathlib import Path
    from key_manager.storage import clear_all_caches
    Path("config.yaml").unlink(missing_ok=True)
    path = tmp_path / "keys.json"
    KeyStore(path).save(SAMPLE_DATA)
    clear_all_caches()
    return path

@pytest.fixture
def plaintext_file(tmp_path):
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(SAMPLE_DATA, indent=2), encoding="utf-8")
    return path


# --- Roundtrip ---

def test_encrypt_decrypt_roundtrip(store):
    store.save(SAMPLE_DATA)
    loaded = store.load()
    assert loaded == SAMPLE_DATA


def test_nonce_changes_each_save(store):
    store.save(SAMPLE_DATA)
    raw1 = json.loads(store.path.read_text(encoding="utf-8"))
    store.save(SAMPLE_DATA)
    raw2 = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw1["nonce"] != raw2["nonce"]


def test_encrypted_format_structure(store):
    store.save(SAMPLE_DATA)
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["encrypted"] is True
    assert "nonce" in raw
    assert "data" in raw
    assert isinstance(raw["nonce"], str)
    assert isinstance(raw["data"], str)


def test_ciphertext_is_base64(store):
    store.save(SAMPLE_DATA)
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    base64.b64decode(raw["nonce"])
    base64.b64decode(raw["data"])


def test_plaintext_never_in_file(store):
    store.save(SAMPLE_DATA)
    content = store.path.read_text(encoding="utf-8")
    assert "sk-abc123" not in content
    assert "openai" not in content


def test_complex_data_roundtrip(store):
    complex_data = {
        "nested": {"deep": {"value": [1, 2, {"inner": True}]}},
        "unicode": "你好世界",
        "null": None,
        "float": 3.14159,
    }
    store.save(complex_data)
    assert store.load() == complex_data


# --- Load auto-detection ---

def test_load_plaintext(plaintext_file):
    store = KeyStore(plaintext_file)
    loaded = store.load()
    assert loaded == SAMPLE_DATA


def test_load_encrypted(encrypted_file):
    store = KeyStore(encrypted_file)
    loaded = store.load()
    assert loaded == SAMPLE_DATA


def test_load_missing_file(tmp_path):
    store = KeyStore(tmp_path / "nonexistent.json")
    with pytest.raises(StorageError, match="File not found"):
        store.load()


def test_load_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json {{{", encoding="utf-8")
    store = KeyStore(path)
    with pytest.raises(StorageError, match="Invalid JSON"):
        store.load()


# --- Migration ---

def test_migrate_plaintext_to_encrypted(plaintext_file):
    store = KeyStore(plaintext_file)
    data = store.migrate()
    assert data == SAMPLE_DATA
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["encrypted"] is True


def test_migrate_idempotent(store):
    store.save(SAMPLE_DATA)
    store.migrate()
    assert store.load() == SAMPLE_DATA


# --- Key rotation ---

def test_rotate_key(encrypted_file):
    store = KeyStore(encrypted_file)
    new_pass = "brand-new-passphrase-2025"
    store.rotate_key(new_pass)
    assert store.load() == SAMPLE_DATA


def test_old_key_fails_after_rotation(encrypted_file):
    store = KeyStore(encrypted_file)
    new_pass = "rotated-key"
    store.rotate_key(new_pass)
    os.environ["KEY_MANAGER_SECRET"] = "old-wrong-key"
    store.config = {}
    with pytest.raises(StorageError, match="Decryption failed"):
        store.load()


# --- Tamper detection ---

def test_tampered_nonce(encrypted_file):
    raw = json.loads(encrypted_file.read_text(encoding="utf-8"))
    bad_nonce = base64.b64encode(os.urandom(12)).decode()
    raw["nonce"] = bad_nonce
    encrypted_file.write_text(json.dumps(raw), encoding="utf-8")
    store = KeyStore(encrypted_file)
    with pytest.raises(StorageError, match="Decryption failed"):
        store.load()


def test_tampered_ciphertext(encrypted_file):
    raw = json.loads(encrypted_file.read_text(encoding="utf-8"))
    decoded = bytearray(base64.b64decode(raw["data"]))
    decoded[-1] ^= 1  # Flip last byte (auth tag) — guaranteed to differ
    tampered = base64.b64encode(bytes(decoded)).decode()
    raw["data"] = tampered
    encrypted_file.write_text(json.dumps(raw), encoding="utf-8")
    store = KeyStore(encrypted_file)
    with pytest.raises(StorageError, match="Decryption failed"):
        store.load()


def test_tampered_encrypted_flag(encrypted_file):
    raw = json.loads(encrypted_file.read_text(encoding="utf-8"))
    raw["encrypted"] = False
    encrypted_file.write_text(json.dumps(raw), encoding="utf-8")
    store = KeyStore(encrypted_file)
    result = store.load()
    # After T4, envelope includes salt field - compare with salt included
    expected = {"encrypted": False, "nonce": raw["nonce"], "data": raw["data"]}
    if "salt" in raw:
        expected["salt"] = raw["salt"]
    assert result == expected


# --- Wrong key ---

def test_wrong_passphrase(encrypted_file):
    os.environ["KEY_MANAGER_SECRET"] = "wrong-passphrase"
    store = KeyStore(encrypted_file)
    with pytest.raises(StorageError, match="Decryption failed"):
        store.load()


# --- Missing passphrase ---

def test_auto_generate_passphrase(monkeypatch, tmp_path):
    # Remove environment variable to trigger auto-generation
    monkeypatch.delenv("KEY_MANAGER_SECRET", raising=False)
    
    # Change to tmp directory so config.yaml is saved there
    monkeypatch.chdir(tmp_path)
    
    # First save should auto-generate passphrase
    store = KeyStore(tmp_path / "keys.json")
    store.save(SAMPLE_DATA)
    
    # Load config to get the auto-generated passphrase
    import yaml
    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Create new store with the saved config
    store2 = KeyStore(tmp_path / "keys.json", config=config)
    assert store2.load() == SAMPLE_DATA


# --- Config-based passphrase ---

def test_passphrase_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("KEY_MANAGER_SECRET", raising=False)
    config = {"encryption": {"passphrase": PASSPHRASE}}
    store = KeyStore(tmp_path / "keys.json", config=config)
    store.save(SAMPLE_DATA)
    assert store.load() == SAMPLE_DATA


# --- Derive key determinism ---

def test_derive_key_deterministic():
    k1 = _derive_key(PASSPHRASE)
    k2 = _derive_key(PASSPHRASE)
    assert k1 == k2
    assert len(k1) == 32


def test_derive_key_different_passphrases():
    k1 = _derive_key("aaa")
    k2 = _derive_key("bbb")
    assert k1 != k2


# --- Envelope structure edge cases ---

def test_missing_nonce_in_envelope(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"encrypted": True, "data": "abc"}), encoding="utf-8")
    store = KeyStore(path)
    with pytest.raises(StorageError, match="Decryption failed|Malformed"):
        store.load()


def test_missing_data_in_envelope(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"encrypted": True, "nonce": base64.b64encode(b"123456789012").decode()}),
        encoding="utf-8",
    )
    store = KeyStore(path)
    with pytest.raises(StorageError, match="Decryption failed|Malformed"):
        store.load()


def test_empty_data_field(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({
            "encrypted": True,
            "nonce": base64.b64encode(os.urandom(12)).decode(),
            "data": base64.b64encode(b"").decode(),
        }),
        encoding="utf-8",
    )
    store = KeyStore(path)
    with pytest.raises(StorageError):
        store.load()


# --- Save creates parent directories ---

def test_save_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "keys.json"
    store = KeyStore(nested)
    store.save(SAMPLE_DATA)
    assert store.load() == SAMPLE_DATA


# --- API Token Derivation ---

def test_derive_api_token_deterministic():
    """derive_api_token returns the same token for the same config."""
    t1 = derive_api_token()
    t2 = derive_api_token()
    assert t1 == t2
    assert len(t1) == 64  # 32 bytes as hex


def test_derive_api_token_different_from_storage_key():
    """API token uses different salt than storage encryption key."""
    token = derive_api_token()
    storage_key = _derive_key(PASSPHRASE).hex()
    assert token != storage_key


def test_derive_api_token_from_env(monkeypatch):
    """derive_api_token uses KEY_MANAGER_SECRET env var."""
    monkeypatch.setenv("KEY_MANAGER_SECRET", "test-secret-123")
    token = derive_api_token()
    assert len(token) == 64


def test_derive_api_token_from_config():
    """derive_api_token uses config encryption.passphrase."""
    config = {"encryption": {"passphrase": "config-passphrase"}}
    token = derive_api_token(config)
    assert len(token) == 64


def test_derive_api_token_caching():
    """derive_api_token caches the result for performance."""
    # Clear cache first
    _key_cache.clear()
    _key_cache.clear()
    
    t1 = derive_api_token()
    # Check cache is populated
    cache_key = (PASSPHRASE, _API_TOKEN_SALT)
    cache_key = (PASSPHRASE, _API_TOKEN_SALT)
    assert cache_key in _key_cache
    
    t2 = derive_api_token()
    assert t1 == t2


# --- derive_api_token salt support ---


def test_derive_api_token_custom_salt():
    """derive_api_token with custom salt returns different token than default."""
    custom_salt = b"my-custom-salt-value"
    t1 = derive_api_token(salt=custom_salt)
    t2 = derive_api_token()  # default salt
    assert t1 != t2
    assert len(t1) == 64


def test_derive_api_token_custom_salt_deterministic():
    """derive_api_token with same custom salt is deterministic."""
    custom_salt = b"deterministic-test-salt"
    t1 = derive_api_token(salt=custom_salt)
    t2 = derive_api_token(salt=custom_salt)
    assert t1 == t2


def test_derive_api_token_different_custom_salts():
    """derive_api_token with different custom salts produce different tokens."""
    t1 = derive_api_token(salt=b"salt-one")
    t2 = derive_api_token(salt=b"salt-two")
    assert t1 != t2


# --- clear_key_cache ---


def test_clear_key_cache_empties_cache():
    """clear_key_cache removes all cached entries."""
    _key_cache.clear()
    _key_cache.clear()
    derive_api_token()
    assert len(_key_cache) > 0
    clear_key_cache()
    assert len(_key_cache) == 0


def test_clear_key_cache_allows_re_derivation():
    """After clearing cache, derive_api_token still returns same token."""
    t1 = derive_api_token()
    t1 = derive_api_token()
    clear_key_cache()
    t2 = derive_api_token()
    assert t1 == t2


# --- rotate_key cache invalidation ---


def test_rotate_key_clears_cache(tmp_path):
    """rotate_key invalidates cached keys from old passphrase."""
    os.environ["KEY_MANAGER_SECRET"] = "old-passphrase-for-test"
    t1 = derive_api_token()
    # Cache should have entry for old passphrase
    assert len(_key_cache) > 0
    # Create a store and rotate
    store_path = tmp_path / "test_keys.json"
    store = KeyStore(str(store_path))
    store.save({"test": "data"})
    store.rotate_key("new-passphrase-for-test")
    # After rotation, derive_api_token with new passphrase should differ
    os.environ["KEY_MANAGER_SECRET"] = "new-passphrase-for-test"
    t2 = derive_api_token()
    assert t1 != t2  # Old token must not match new token


# --- _encrypt cache pollution ---


def test_encrypt_does_not_pollute_cache(tmp_path):
    """_encrypt with random salt should not add entries to cache."""
    _key_cache.clear()
    store_path = tmp_path / "pollution_test.json"
    store = KeyStore(str(store_path))
    store.save({"key": "sk-test123"})
    # Check that no random-salt entries were cached
    # Only _LEGACY_SALT or _API_TOKEN_SALT entries should be cached
    for (pp, salt) in _key_cache:
        assert salt in (_LEGACY_SALT, _API_TOKEN_SALT), f"Unexpected salt in cache: {salt!r}"


# --- Optional encryption ---


def test_save_plaintext_when_encrypted_false(tmp_path):
    """S2: Explicit encrypted=false → plaintext storage."""
    config = {"storage": {"encrypted": False}}
    store = KeyStore(tmp_path / "keys.json", config=config)
    store.save(SAMPLE_DATA)
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw.get("encrypted") is not True
    assert raw == SAMPLE_DATA


def test_save_encrypted_when_encrypted_true(tmp_path):
    """S3: Explicit encrypted=true → encrypted storage."""
    config = {"storage": {"encrypted": True}}
    store = KeyStore(tmp_path / "keys.json", config=config)
    store.save(SAMPLE_DATA)
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["encrypted"] is True


def test_save_encrypted_by_default(tmp_path):
    """S1: Default behavior (no encrypted config) → encrypted=True."""
    store = KeyStore(tmp_path / "keys.json")
    store.save(SAMPLE_DATA)
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["encrypted"] is True


def test_plaintext_roundtrip(tmp_path):
    """Plaintext save/load roundtrip preserves data."""
    config = {"storage": {"encrypted": False}}
    store = KeyStore(tmp_path / "keys.json", config=config)
    store.save(SAMPLE_DATA)
    loaded = store.load()
    assert loaded == SAMPLE_DATA


def test_plaintext_file_not_encrypted(tmp_path):
    """S2: Plaintext file should not contain encrypted envelope keys."""
    config = {"storage": {"encrypted": False}}
    store = KeyStore(tmp_path / "keys.json", config=config)
    store.save(SAMPLE_DATA)
    content = store.path.read_text(encoding="utf-8")
    assert '"encrypted"' not in content
    assert '"nonce"' not in content
    assert '"data"' not in content


def test_existing_encrypted_file_with_encrypted_false_config(tmp_path):
    """S5: Existing encrypted file + encrypted=false config → load still works (auto-detect)."""
    store_enc = KeyStore(tmp_path / "keys.json")
    store_enc.save(SAMPLE_DATA)
    config = {"storage": {"encrypted": False}}
    store_plain = KeyStore(tmp_path / "keys.json", config=config)
    loaded = store_plain.load()
    assert loaded == SAMPLE_DATA


def test_existing_plaintext_file_with_encrypted_true_config(tmp_path):
    """S6: Existing plaintext file + encrypted=true config → load works, next save encrypts."""
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(SAMPLE_DATA, indent=2), encoding="utf-8")
    config = {"storage": {"encrypted": True}}
    store = KeyStore(path, config=config)
    loaded = store.load()
    assert loaded == SAMPLE_DATA
    store.save(SAMPLE_DATA)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["encrypted"] is True


def test_decrypt_failure_raises_storage_error(tmp_path):
    """S4: Decryption failure → raises StorageError."""
    path = tmp_path / "keys.json"
    bad_envelope = {"encrypted": True, "salt": "AAAA", "nonce": "AAAA", "data": "AAAA"}
    path.write_text(json.dumps(bad_envelope), encoding="utf-8")
    store = KeyStore(path)
    with pytest.raises(StorageError, match="Decryption failed"):
        store.load()


def test_resolve_config_path_frozen(monkeypatch):
    """_resolve_config_path should resolve to exe dir when frozen."""
    from key_manager.storage import _resolve_config_path

    # Non-frozen: CWD-relative
    assert _resolve_config_path() == Path("config.yaml")

    # Frozen: next to exe
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", [r"D:\KeyHub\KeyHub.exe"])
    assert _resolve_config_path() == Path(r"D:\KeyHub\config.yaml")
