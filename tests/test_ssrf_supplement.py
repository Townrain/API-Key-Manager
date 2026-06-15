"""Supplementary tests for ssrf.py - get_allowed_domains function."""
import pytest

from key_manager.ssrf import validate_custom_base_url, get_allowed_domains
from key_manager.errors import ValidationError


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
