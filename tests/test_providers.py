"""Parameterized provider contract tests."""

import pytest
from key_manager.providers import PROVIDERS


REPRESENTATIVE = list(PROVIDERS.keys())


@pytest.mark.parametrize("name", REPRESENTATIVE)
def test_provider_has_name(name):
    """Provider name is non-empty string."""
    provider = PROVIDERS[name]
    assert isinstance(provider.name, str)
    assert len(provider.name) > 0


@pytest.mark.parametrize("name", REPRESENTATIVE)
def test_provider_has_base_url(name):
    """Provider base_url starts with https://."""
    provider = PROVIDERS[name]
    assert provider.base_url.startswith("https://")


@pytest.mark.parametrize("name", REPRESENTATIVE)
def test_provider_has_check_endpoint(name):
    """Provider check_endpoint is non-empty."""
    provider = PROVIDERS[name]
    assert isinstance(provider.check_endpoint, str)
    assert len(provider.check_endpoint) > 0


@pytest.mark.parametrize("name", REPRESENTATIVE)
def test_provider_build_headers(name):
    """Provider build_headers returns dict with auth header."""
    provider = PROVIDERS[name]
    headers = provider.build_headers("test-key-123")
    assert isinstance(headers, dict)
    # Should have some auth header (Authorization or x-api-key)
    has_auth = any(
        k.lower() in ("authorization", "x-api-key", "api-key")
        for k in headers.keys()
    )
    # Google passes key via URL param, not header
    if name == "google":
        pytest.skip("Google uses URL param for auth, not headers")
    assert has_auth, f"No auth header found in {list(headers.keys())}"


@pytest.mark.parametrize("name", REPRESENTATIVE)
def test_provider_get_base_url(name):
    """Provider get_base_url returns valid URL."""
    provider = PROVIDERS[name]
    url = provider.get_base_url()
    assert url.startswith("https://")
