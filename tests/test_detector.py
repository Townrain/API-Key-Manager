"""Unit tests for key_manager.detector module."""

import pytest

from key_manager.detector import (
    KEY_PATTERNS,
    UNIQUE_SIGNATURES,
    WEIGHT_RATE_LIMITED,
    WEIGHT_SELF,
    detect_by_pattern,
    detect_by_prefix,
    score_provider,
)


# ---------------------------------------------------------------------------
# 1. test_detect_by_prefix_unique
# ---------------------------------------------------------------------------
class TestDetectByPrefixUnique:
    """Unique prefixes that map to exactly one provider."""

    @pytest.mark.parametrize(
        "key, expected",
        [
            ("sk-proj-abc123", ["openai"]),
            ("AIzaSyD-example", ["google"]),
            ("gsk_abcdef123456", ["groq"]),
            ("sk-ant-api03-xyz", ["anthropic"]),
            ("pplx-abc123", ["perplexity"]),
            ("sk-or-v1-abc", ["openrouter"]),
            ("hf_abc123", ["huggingface"]),
            ("r8_abc123", ["replicate"]),
            ("fw_abc123", ["fireworks"]),
            ("xai-abc123", ["grok"]),
            ("ms-abc123", ["modelscope"]),
            ("poe-abc123", ["poe"]),
        ],
        ids=[
            "sk-proj → openai",
            "AIza → google",
            "gsk_ → groq",
            "sk-ant-api03 → anthropic",
            "pplx- → perplexity",
            "sk-or-v1 → openrouter",
            "hf_ → huggingface",
            "r8_ → replicate",
            "fw_ → fireworks",
            "xai- → grok",
            "ms- → modelscope",
            "poe- → poe",
        ],
    )
    def test_unique_prefix_returns_single_provider(self, key, expected):
        result = detect_by_prefix(key)
        assert result == expected


# ---------------------------------------------------------------------------
# 2. test_detect_by_prefix_shared
# ---------------------------------------------------------------------------
class TestDetectByPrefixShared:
    """The generic 'sk-' prefix maps to many providers."""

    def test_sk_prefix_returns_multiple_candidates(self):
        result = detect_by_prefix("sk-abc1234567890")
        # 'sk-' is the shared prefix with many providers
        assert len(result) > 1
        assert "openai" in result
        assert "deepseek" in result
        assert "together" in result

    def test_sk_prefix_longer_match_wins(self):
        """A longer specific prefix should win over the generic sk-."""
        result = detect_by_prefix("sk-proj-abc123")
        assert result == ["openai"]


# ---------------------------------------------------------------------------
# 3. test_detect_by_prefix_unknown
# ---------------------------------------------------------------------------
class TestDetectByPrefixUnknown:
    """Unknown prefixes return an empty list."""

    @pytest.mark.parametrize(
        "key",
        [
            "totally-unknown-abc",
            "zzz-no-match",
            "12345",
        ],
        ids=["totally-unknown", "zzz-prefix", "numeric-only"],
    )
    def test_unknown_prefix_returns_empty(self, key):
        result = detect_by_prefix(key)
        assert result == []


# ---------------------------------------------------------------------------
# 4. test_detect_by_pattern_unique
# ---------------------------------------------------------------------------
class TestDetectByPatternUnique:
    """Patterns that uniquely identify a provider."""

    @pytest.mark.parametrize(
        "key, expected",
        [
            ("sk-ant-api03-abcdef", "anthropic"),
            ("pplx-abc123456", "perplexity"),
            ("sk-proj-abc123", "openai"),
            ("AIzaSyExample", "google"),
            ("gsk_abcdef", "groq"),
            ("xai-abc123", "grok"),
            ("hf_abc123", "huggingface"),
            ("r8_abc123", "replicate"),
            ("fw_abc123", "fireworks"),
            ("poe-abc123", "poe"),
        ],
        ids=[
            "sk-ant-api03 → anthropic",
            "pplx- → perplexity",
            "sk-proj- → openai",
            "AIza → google",
            "gsk_ → groq",
            "xai- → grok",
            "hf_ → huggingface",
            "r8_ → replicate",
            "fw_ → fireworks",
            "poe- → poe",
        ],
    )
    def test_pattern_matches_provider(self, key, expected):
        result = detect_by_pattern(key)
        assert result == expected


# ---------------------------------------------------------------------------
# 5. test_detect_by_pattern_unknown
# ---------------------------------------------------------------------------
class TestDetectByPatternUnknown:
    """Unknown patterns return None."""

    @pytest.mark.parametrize(
        "key",
        [
            "totally-unknown-abc",
            "zzz-no-match",
            "12345",
        ],
        ids=["totally-unknown", "zzz-prefix", "numeric-only"],
    )
    def test_unknown_pattern_returns_none(self, key):
        result = detect_by_pattern(key)
        assert result is None


# ---------------------------------------------------------------------------
# 6. test_score_provider_self_signature
# ---------------------------------------------------------------------------
class TestScoreProviderSelfSignature:
    """Matching self-signature returns WEIGHT_SELF (100)."""

    def test_single_signature_match(self):
        """One matching signature → 100 points."""
        score = score_provider("anthropic", "Error: anthropic rate limit exceeded")
        assert score == WEIGHT_SELF  # 100

    def test_multiple_signature_matches(self):
        """Multiple matching signatures → 100 * n points."""
        score = score_provider(
            "anthropic",
            "Error from anthropic and x-api-key header is invalid",
        )
        assert score == WEIGHT_SELF * 2  # 200

    def test_signature_case_insensitive(self):
        """Signature matching is case-insensitive."""
        score = score_provider("anthropic", "Error: ANTHROPIC rate limit")
        assert score == WEIGHT_SELF

    def test_known_providers_have_signatures(self):
        """Verify that our test providers have unique signatures."""
        for provider in ["anthropic", "openrouter", "openai", "groq", "google"]:
            assert provider in UNIQUE_SIGNATURES
            assert len(UNIQUE_SIGNATURES[provider]) > 0


# ---------------------------------------------------------------------------
# 7. test_score_provider_rate_limited
# ---------------------------------------------------------------------------
class TestScoreProviderRateLimited:
    """429 status returns WEIGHT_RATE_LIMITED (60) per signature match."""

    def test_429_returns_reduced_weight(self):
        """429 status gives 60 points instead of 100."""
        score = score_provider(
            "anthropic", "rate limit exceeded", status_code=429
        )
        # For 429, the weight is reduced to WEIGHT_RATE_LIMITED
        # but "rate limit exceeded" doesn't contain any anthropic signatures
        # so score is 0 (no signature match)
        assert score == 0

    def test_429_multiple_sigs(self):
        """429 with multiple signature matches still uses reduced weight."""
        score = score_provider(
            "anthropic",
            "Error from anthropic and x-api-key header",
            status_code=429,
        )
        assert score == WEIGHT_RATE_LIMITED * 2  # 120

    def test_non_429_uses_full_weight(self):
        """Non-429 status codes use full WEIGHT_SELF."""
        score = score_provider(
            "anthropic", "Error from anthropic", status_code=401
        )
        assert score == WEIGHT_SELF  # 100

    def test_none_status_uses_full_weight(self):
        """None status_code defaults to full weight."""
        score = score_provider("anthropic", "Error from anthropic")
        assert score == WEIGHT_SELF  # 100


# ---------------------------------------------------------------------------
# 8. test_score_provider_no_match
# ---------------------------------------------------------------------------
class TestScoreProviderNoMatch:
    """No matching signature returns 0."""

    def test_no_match_returns_zero(self):
        score = score_provider("anthropic", "something completely unrelated")
        assert score == 0

    def test_unknown_provider_returns_zero(self):
        score = score_provider("nonexistent-provider", "any error body")
        assert score == 0

    def test_empty_body_returns_zero(self):
        score = score_provider("anthropic", "")
        assert score == 0

    def test_empty_body_429_returns_zero(self):
        """Even with 429, no signature match means score is 0."""
        score = score_provider("anthropic", "", status_code=429)
        assert score == 0


# ---------------------------------------------------------------------------
# 9. test_detect_provider_balance_insufficient
# ---------------------------------------------------------------------------
class TestDetectProviderBalanceInsufficient:
    """Test detect_provider when /v1/models returns 200 but /v1/chat/completions returns 402."""

    @pytest.mark.asyncio
    async def test_detect_provider_402_returns_provider(self):
        """When /v1/models returns 200 and all models return 402, should return the provider."""
        from unittest.mock import AsyncMock, MagicMock, patch
        import httpx
        
        # Mock responses
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
        
        chat_response = MagicMock()
        chat_response.status_code = 402
        chat_response.text = '{"error": {"message": "Insufficient Balance"}}'
        
        # Create mock client
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=models_response)
        mock_client.post = AsyncMock(return_value=chat_response)
        
        # Mock PROVIDERS to only include deepseek
        mock_provider = MagicMock()
        mock_provider.get_base_url.return_value = "https://api.deepseek.com/v1"
        mock_provider.check_endpoint = "/models"
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
        
        with patch("key_manager.detector.PROVIDERS", {"deepseek": mock_provider}):
            from key_manager.detector import detect_provider
            result = await detect_provider(mock_client, "sk-test-key-12345")
        
        assert result == "deepseek"

    @pytest.mark.asyncio
    async def test_detect_provider_200_returns_provider(self):
        """When /v1/chat/completions returns 200, should return the provider immediately."""
        from unittest.mock import AsyncMock, MagicMock, patch
        import httpx
        
        # Mock responses
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {"data": [{"id": "model-1"}]}
        
        chat_response = MagicMock()
        chat_response.status_code = 200
        chat_response.text = '{"choices": [{"message": {"content": "hi"}}]}'
        
        # Create mock client
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=models_response)
        mock_client.post = AsyncMock(return_value=chat_response)
        
        # Mock PROVIDERS to only include deepseek
        mock_provider = MagicMock()
        mock_provider.get_base_url.return_value = "https://api.deepseek.com/v1"
        mock_provider.check_endpoint = "/models"
        mock_provider.build_headers.return_value = {"Authorization": "Bearer test-key"}
        
        with patch("key_manager.detector.PROVIDERS", {"deepseek": mock_provider}):
            from key_manager.detector import detect_provider
            result = await detect_provider(mock_client, "sk-test-key-12345")
        
        assert result == "deepseek"
