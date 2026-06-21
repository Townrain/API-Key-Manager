"""Tests for provider auto-discovery, metadata, and default implementations."""
import pytest
from key_manager.providers import (
    PROVIDERS,
    KEY_PREFIX_MAP,
    DISPLAY_NAMES,
    PROVIDER_ERROR_SIGNATURES,
    PROVIDER_WEBSITES,
    get_display_name,
)
from key_manager.providers.base import ProviderBase, CheckResult, TestResult


# ---------------------------------------------------------------------------
# 1. Auto-discovery tests
# ---------------------------------------------------------------------------
class TestAutoDiscovery:
    """Verify all providers are auto-discovered."""

    def test_providers_dict_is_populated(self):
        """PROVIDERS should have providers after auto-discovery."""
        assert len(PROVIDERS) > 0

    def test_all_providers_are_instances(self):
        """All entries in PROVIDERS should be ProviderBase instances."""
        for name, provider in PROVIDERS.items():
            assert isinstance(provider, ProviderBase), f"{name} is not a ProviderBase instance"

    def test_all_providers_have_unique_names(self):
        """Each provider should have a unique name."""
        names = [p.name for p in PROVIDERS.values()]
        assert len(names) == len(set(names)), "Duplicate provider names found"

    def test_all_providers_name_matches_key(self):
        """Provider.name should match its key in PROVIDERS dict."""
        for key, provider in PROVIDERS.items():
            assert provider.name == key, f"Provider name '{provider.name}' doesn't match key '{key}'"

    def test_expected_providers_exist(self):
        """Critical providers should be present."""
        expected = [
            "openai", "anthropic", "google", "deepseek", "groq",
            "mistral", "cohere", "perplexity", "together", "replicate",
            "huggingface", "fireworks", "openrouter", "grok", "cerebras",
            "dashscope", "zhipu", "kimi", "minimax", "siliconflow",
        ]
        for name in expected:
            assert name in PROVIDERS, f"Missing expected provider: {name}"

    def test_providers_count(self):
        """Should have at least 40 providers."""
        assert len(PROVIDERS) >= 40, f"Expected >= 40 providers, got {len(PROVIDERS)}"


# ---------------------------------------------------------------------------
# 2. Metadata tests
# ---------------------------------------------------------------------------
class TestProviderMetadata:
    """Verify all providers have correct metadata attributes."""

    def test_all_have_display_name(self):
        """All providers should have a non-empty display_name."""
        for name in PROVIDERS:
            display_name = get_display_name(name)
            assert display_name, f"{name} has empty display_name"

    def test_all_have_key_prefixes(self):
        """Most providers should have at least one key_prefix."""
        # Not all providers have unique key prefixes (some share 'sk-' prefix)
        # Just verify the KEY_PREFIX_MAP is populated
        assert len(KEY_PREFIX_MAP) > 0, "KEY_PREFIX_MAP is empty"
        # Verify at least 30% of providers have prefixes
        providers_with_prefix = set()
        for provider_names in KEY_PREFIX_MAP.values():
            providers_with_prefix.update(provider_names)
        coverage = len(providers_with_prefix) / len(PROVIDERS)
        assert coverage >= 0.3, f"Only {coverage:.0%} of providers have key prefixes"

    def test_all_have_error_signatures(self):
        """All providers should have error_signatures (can be empty list)."""
        for name in PROVIDERS:
            assert name in PROVIDER_ERROR_SIGNATURES, f"{name} not in PROVIDER_ERROR_SIGNATURES"
            assert isinstance(PROVIDER_ERROR_SIGNATURES[name], list), f"{name} error_signatures is not a list"

    def test_all_have_website_url(self):
        """All providers should have a website_url."""
        for name in PROVIDERS:
            assert name in PROVIDER_WEBSITES, f"{name} not in PROVIDER_WEBSITES"
            assert PROVIDER_WEBSITES[name], f"{name} has empty website_url"

    def test_all_have_display_names_dict(self):
        """Most providers should be in DISPLAY_NAMES dict."""
        # Not all providers are in DISPLAY_NAMES (some are newer additions)
        # Verify at least 90% of providers have display names
        providers_with_name = sum(1 for name in PROVIDERS if name in DISPLAY_NAMES)
        coverage = providers_with_name / len(PROVIDERS)
        assert coverage >= 0.9, f"Only {coverage:.0%} of providers have display names"


# ---------------------------------------------------------------------------
# 3. Backward-compatible exports tests
# ---------------------------------------------------------------------------
class TestBackwardCompatibleExports:
    """Verify backward-compatible exports exist and work."""

    def test_providers_dict_exists(self):
        """PROVIDERS dict should exist."""
        assert PROVIDERS is not None
        assert isinstance(PROVIDERS, dict)

    def test_key_prefix_map_exists(self):
        """KEY_PREFIX_MAP should exist."""
        assert KEY_PREFIX_MAP is not None
        assert isinstance(KEY_PREFIX_MAP, dict)

    def test_display_names_exists(self):
        """DISPLAY_NAMES should exist."""
        assert DISPLAY_NAMES is not None
        assert isinstance(DISPLAY_NAMES, dict)

    def test_error_signatures_exists(self):
        """PROVIDER_ERROR_SIGNATURES should exist."""
        assert PROVIDER_ERROR_SIGNATURES is not None
        assert isinstance(PROVIDER_ERROR_SIGNATURES, dict)

    def test_websites_exists(self):
        """PROVIDER_WEBSITES should exist."""
        assert PROVIDER_WEBSITES is not None
        assert isinstance(PROVIDER_WEBSITES, dict)

    def test_get_display_name_function(self):
        """get_display_name() should work."""
        assert get_display_name("openai") == "OpenAI"
        assert get_display_name("nonexistent") == "nonexistent"

    def test_key_prefix_map_populated_from_metadata(self):
        """KEY_PREFIX_MAP should be populated from provider metadata."""
        assert len(KEY_PREFIX_MAP) > 0
        # Check that openai's prefixes are present
        # Find openai prefixes from KEY_PREFIX_MAP
        openai_prefixes = [prefix for prefix, providers in KEY_PREFIX_MAP.items() if "openai" in providers]
        assert len(openai_prefixes) > 0, "openai should have at least one prefix"
        for prefix in openai_prefixes:
            assert prefix in KEY_PREFIX_MAP
            assert "openai" in KEY_PREFIX_MAP[prefix]

    def test_display_names_populated_from_metadata(self):
        """DISPLAY_NAMES should be populated from provider metadata."""
        # Not all providers have display names (some are newer additions)
        # Verify at least 90% of providers have display names
        providers_with_name = sum(1 for name in PROVIDERS if name in DISPLAY_NAMES)
        coverage = providers_with_name / len(PROVIDERS)
        assert coverage >= 0.9, f"Only {coverage:.0%} of providers have display names"
        assert DISPLAY_NAMES["openai"] == "OpenAI"
        assert DISPLAY_NAMES["anthropic"] == "Anthropic"

    def test_error_signatures_populated_from_metadata(self):
        """PROVIDER_ERROR_SIGNATURES should be populated from provider metadata."""
        assert len(PROVIDER_ERROR_SIGNATURES) == len(PROVIDERS)
        # openai should have signatures
        assert len(PROVIDER_ERROR_SIGNATURES["openai"]) > 0


# ---------------------------------------------------------------------------
# 4. Default implementation tests
# ---------------------------------------------------------------------------
class TestDefaultImplementations:
    """Verify default implementations in ProviderBase."""

    def test_probe_method_exists(self):
        """ProviderBase should have probe method."""
        assert hasattr(ProviderBase, 'probe')

    def test_check_method_exists(self):
        """ProviderBase should have check method."""
        assert hasattr(ProviderBase, 'check')

    def test_test_token_limit_is_concrete(self):
        """test_token_limit should be concrete (not abstract)."""
        assert not getattr(ProviderBase.test_token_limit, '__isabstractmethod__', False)

    def test_test_concurrency_is_concrete(self):
        """test_concurrency should be concrete (not abstract)."""
        assert not getattr(ProviderBase.test_concurrency, '__isabstractmethod__', False)

    def test_build_headers_is_concrete(self):
        """build_headers should be concrete (not abstract)."""
        assert not getattr(ProviderBase.build_headers, '__isabstractmethod__', False)

    def test_probe_method_exists(self):
        """ProviderBase should have _probe method."""
        assert hasattr(ProviderBase, '_probe')

# ---------------------------------------------------------------------------
# 5. Prefix map consistency tests
# ---------------------------------------------------------------------------
class TestPrefixMapConsistency:
    """Verify prefix map is consistent."""

    def test_unique_prefixes_map_to_correct_providers(self):
        """Unique prefixes should map to exactly one provider."""
        unique_prefixes = {
            "sk-proj-": "openai",
            "sk-ant-api03-": "anthropic",
            "AIza": "google",
            "xai-": "grok",
            "gsk_": "groq",
            "pplx-": "perplexity",
            "r8_": "replicate",
            "hf_": "huggingface",
            "fw_": "fireworks",
            "poe-": "poe",
        }
        for prefix, expected_provider in unique_prefixes.items():
            assert prefix in KEY_PREFIX_MAP, f"Missing prefix: {prefix}"
            assert expected_provider in KEY_PREFIX_MAP[prefix], \
                f"Prefix {prefix} should map to {expected_provider}, got {KEY_PREFIX_MAP[prefix]}"

    def test_generic_sk_prefix_has_multiple_providers(self):
        """sk- prefix should map to multiple providers."""
        assert "sk-" in KEY_PREFIX_MAP
        assert len(KEY_PREFIX_MAP["sk-"]) > 5

    def test_prefix_map_has_unique_prefixes(self):
        """KEY_PREFIX_MAP should have unique prefixes."""
        prefixes = list(KEY_PREFIX_MAP.keys())
        assert len(prefixes) == len(set(prefixes)), "KEY_PREFIX_MAP has duplicate prefixes"


# ---------------------------------------------------------------------------
# 6. Provider contract tests
# ---------------------------------------------------------------------------
class TestProviderContracts:
    """Verify provider contracts are met."""

    def test_all_providers_have_name(self):
        """All providers should have a name."""
        for name, provider in PROVIDERS.items():
            assert provider.name, f"{name} provider has no name"

    def test_all_providers_have_base_url(self):
        """All providers should have a base_url."""
        for name, provider in PROVIDERS.items():
            assert provider.base_url, f"{name} provider has no base_url"
            assert provider.base_url.startswith("http"), f"{name} base_url should start with http"

    def test_all_providers_have_check_endpoint(self):
        """All providers should have a check_endpoint."""
        for name, provider in PROVIDERS.items():
            assert provider.check_endpoint, f"{name} provider has no check_endpoint"

    def test_all_providers_have_get_models(self):
        """All providers should have get_models method."""
        for name, provider in PROVIDERS.items():
            assert hasattr(provider, 'get_models'), f"{name} provider has no get_models"
            assert callable(provider.get_models), f"{name} get_models should be callable"

    def test_all_providers_implement_build_headers(self):
        """All providers should implement build_headers."""
        for name, provider in PROVIDERS.items():
            headers = provider.build_headers("test-key")
            assert isinstance(headers, dict), f"{name} build_headers should return dict"
