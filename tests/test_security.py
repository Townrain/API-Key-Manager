"""Security regression tests."""

import json
import os
import pytest
from pathlib import Path
from key_manager.storage import KeyStore
from key_manager.parser import validate_import_path
from key_manager.ssrf import validate_custom_base_url, get_allowed_domains
from key_manager.errors import ValidationError

class TestRandomSalt:
    """T4: Random PBKDF2 salt per installation."""

    def test_random_salt_per_encryption(self, tmp_path):
        """Two saves produce different salt values."""
        os.environ["KEY_MANAGER_SECRET"] = "test-secret"
        store = KeyStore(str(tmp_path / "keys.json"))

        store.save({"keys": {"k1": {"v": 1}}})
        raw1 = json.loads((tmp_path / "keys.json").read_text())

        store.save({"keys": {"k1": {"v": 2}}})
        raw2 = json.loads((tmp_path / "keys.json").read_text())

        assert "salt" in raw1
        assert "salt" in raw2
        assert raw1["salt"] != raw2["salt"]

    def test_legacy_salt_backward_compat(self, tmp_path):
        """Old files without salt field still decrypt."""
        os.environ["KEY_MANAGER_SECRET"] = "test-secret"

        from key_manager.storage import _derive_key, _LEGACY_SALT, _NONCE_LEN, _b64e
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        passphrase = "test-secret"
        key = _derive_key(passphrase, _LEGACY_SALT)
        nonce = os.urandom(_NONCE_LEN)
        data = {"keys": {"legacy": {"v": 1}}}
        plaintext = json.dumps(data).encode("utf-8")
        aes = AESGCM(key)
        ciphertext = aes.encrypt(nonce, plaintext, None)

        envelope = {
            "encrypted": True,
            "nonce": _b64e(nonce),
            "data": _b64e(ciphertext),
        }
        (tmp_path / "keys.json").write_text(json.dumps(envelope))

        store = KeyStore(str(tmp_path / "keys.json"))
        result = store.load()
        assert result == data


class TestPathTraversal:
    """T2: Path traversal prevention."""

    def test_validate_import_path_blocks_traversal(self):
        """Path traversal is blocked."""
        with pytest.raises(ValidationError):
            validate_import_path("../../etc/passwd", ["./data/input"])

    def test_validate_import_path_blocks_absolute(self):
        """Absolute path outside allowed dirs is blocked."""
        with pytest.raises(ValidationError):
            validate_import_path("/etc/passwd", ["./data/input"])

    def test_validate_import_path_allows_valid(self, tmp_path):
        """Valid path within allowed dirs passes."""
        allowed = tmp_path / "data"
        allowed.mkdir(parents=True, exist_ok=True)
        test_file = allowed / "test.json"
        test_file.write_text("{}")
        result = validate_import_path(str(test_file), [str(allowed)])
        assert isinstance(result, Path), "Should return a Path object"
        assert result == test_file


class TestSSRFProtection:
    """T3: SSRF protection."""

    def test_ssrf_blocks_localhost(self):
        """Localhost is blocked."""
        with pytest.raises(ValidationError, match="Localhost"):
            validate_custom_base_url("http://localhost:8080/api", set())

    def test_ssrf_blocks_private_ip(self):
        """Private IP is blocked."""
        with pytest.raises(ValidationError, match="Private"):
            validate_custom_base_url("http://192.168.1.1/api", set())

    def test_ssrf_blocks_metadata_endpoint(self):
        """Cloud metadata endpoint is blocked."""
        with pytest.raises(ValidationError, match="Private"):
            validate_custom_base_url("http://169.254.169.254/latest/meta-data", set())

    def test_ssrf_blocks_file_scheme(self):
        """file:// scheme is blocked."""
        with pytest.raises(ValidationError, match="http/https"):
            validate_custom_base_url("file:///etc/passwd", set())

    def test_ssrf_allows_valid_domain(self):
        """Valid domain in allowlist passes."""
        domains = {"api.openai.com"}
        result = validate_custom_base_url("https://api.openai.com/v1", domains)
        assert result == "https://api.openai.com/v1"

    def test_ssrf_blocks_unknown_domain(self):
        """Domain not in allowlist is blocked."""
        with pytest.raises(ValidationError, match="not in allowed"):
            validate_custom_base_url("https://evil.com/api", {"api.openai.com"})


class TestAuthWarning:
    """T6: Auth-disabled warning."""

    def test_auth_timing_attack_protection(self):
        """Auth middleware uses hmac.compare_digest for timing-safe comparison."""
        import inspect
        from key_manager.web import auth_middleware
        source = inspect.getsource(auth_middleware)
        assert "hmac.compare_digest" in source, "Auth middleware should use hmac.compare_digest()"


class TestGetAllowedDomains:
    """Tests for get_allowed_domains function."""

    def test_extract_domains_from_providers(self):
        """Extract domains from provider base URLs."""
        # Mock providers with base_url
        class MockProvider:
            def __init__(self, base_url):
                self.base_url = base_url

        providers = {
            "openai": MockProvider("https://api.openai.com/v1"),
            "anthropic": MockProvider("https://api.anthropic.com"),
            "google": MockProvider("https://generativelanguage.googleapis.com"),
        }

        domains = get_allowed_domains(providers)
        assert "api.openai.com" in domains
        assert "api.anthropic.com" in domains
        assert "generativelanguage.googleapis.com" in domains

    def test_extract_domains_empty_providers(self):
        """Empty providers returns empty set."""
        domains = get_allowed_domains({})
        assert domains == set()

    def test_extract_domains_no_hostname(self):
        """Provider with no hostname is skipped."""
        class MockProvider:
            base_url = ""

        providers = {"test": MockProvider()}
        domains = get_allowed_domains(providers)
        assert len(domains) == 0


class TestValidateCustomBaseUrl:
    """Tests for validate_custom_base_url function."""

    def test_valid_https_url(self, tmp_path):
        """Valid HTTPS URL passes validation."""
        allowed_domains = {"api.example.com", "custom.proxy.com"}
        result = validate_custom_base_url("https://api.example.com/v1", allowed_domains)
        assert result == "https://api.example.com/v1"

    def test_valid_http_url(self, tmp_path):
        """Valid HTTP URL passes validation."""
        allowed_domains = {"api.example.com"}
        result = validate_custom_base_url("http://api.example.com/v1", allowed_domains)
        assert result == "http://api.example.com/v1"

    def test_invalid_scheme(self, tmp_path):
        """Non-http/https scheme raises error."""
        allowed_domains = {"api.example.com"}
        with pytest.raises(ValidationError):
            validate_custom_base_url("ftp://api.example.com", allowed_domains)

    def test_localhost_blocked(self, tmp_path):
        """Localhost URLs are blocked."""
        allowed_domains = {"api.example.com"}
        with pytest.raises(ValidationError):
            validate_custom_base_url("http://localhost:8080", allowed_domains)

    def test_private_ip_blocked(self, tmp_path):
        """Private IP addresses are blocked."""
        allowed_domains = {"api.example.com"}
        with pytest.raises(ValidationError):
            validate_custom_base_url("http://192.168.1.1", allowed_domains)

    def test_domain_not_in_whitelist(self, tmp_path):
        """Domain not in whitelist raises error."""
        allowed_domains = {"api.example.com"}
        with pytest.raises(ValidationError):
            validate_custom_base_url("https://evil.com/v1", allowed_domains)
