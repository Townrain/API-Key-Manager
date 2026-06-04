import base64
import json
import os

import pytest

from key_manager.storage import KeyStore, StorageError, _derive_key, _get_passphrase


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
    path = tmp_path / "keys.json"
    KeyStore(path).save(SAMPLE_DATA)
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
    decoded = base64.b64decode(raw["data"])
    tampered = base64.b64encode(decoded[:4] + b"\x00" + decoded[5:]).decode()
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

def test_no_passphrase_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("KEY_MANAGER_SECRET", raising=False)
    store = KeyStore(tmp_path / "keys.json")
    with pytest.raises(StorageError, match="No passphrase found"):
        store.save(SAMPLE_DATA)


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
