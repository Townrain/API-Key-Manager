"""Comprehensive unit tests for key_manager/detector.py.

Acts as a regression safety net for the detection logic. Covers:
- Pure functions: detect_by_prefix, detect_by_format, score_provider
- Main async flow: detect_provider (suspected_provider, format, prefix, probing, signatures)
- Helper functions: _try_provider, _try_unknown_provider

All tests use mocks — no real network calls. asyncio_mode = "auto" (no @pytest.mark.asyncio).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.detector import (
    _try_provider,
    _try_unknown_provider,
    detect_by_format,
    detect_by_prefix,
    detect_provider,
    score_provider,
)


# ── Class 1: TestDetectByPrefix (5 tests, pure function) ────────────────────


class TestDetectByPrefix:
    """Tests for detect_by_prefix() — pure function, no mocks needed."""

    def test_unique_prefix_returns_single(self):
        """sk-proj- prefix uniquely identifies OpenAI."""
        result = detect_by_prefix("sk-proj-test123456789")
        assert result == ["openai"]

    def test_shared_prefix_returns_multiple(self):
        """sk- prefix matches 21+ providers."""
        result = detect_by_prefix("sk-test123456789")
        assert len(result) > 20
        assert "openai" in result
        assert "deepseek" in result

    def test_no_match_returns_empty(self):
        """Unknown prefix returns empty list."""
        result = detect_by_prefix("unknown-prefix-test123")
        assert result == []

    def test_longest_prefix_wins(self):
        """sk-ant-api03- (13 chars) beats sk- (3 chars) for anthropic keys."""
        result = detect_by_prefix("sk-ant-api03-test123456789")
        assert result == ["anthropic"]

    def test_special_prefixes(self):
        """Non-sk prefixes work: AIza→google, gsk_→groq."""
        assert detect_by_prefix("AIzaSyExample123456789") == ["google"]
        assert detect_by_prefix("gsk_test123456789") == ["groq"]


# ── Class 2: TestDetectByFormat (5 tests, pure function) ────────────────────


class TestDetectByFormat:
    """Tests for detect_by_format() — pure function, no mocks needed."""

    def test_zhipu_format_returns_candidates(self):
        """Zhipu {id}.{secret} format returns ["zhipu", "zai"]."""
        key = "a" * 30 + "." + "b" * 20  # id=30, secret=20, both alphanumeric
        result = detect_by_format(key)
        assert result == ["zhipu", "zai"]

    def test_normal_key_returns_empty(self):
        """Normal sk- key returns empty list."""
        assert detect_by_format("sk-test123456789") == []

    def test_short_id_returns_empty(self):
        """ID part < 20 chars returns empty."""
        key = "a" * 5 + "." + "b" * 20  # id too short
        assert detect_by_format(key) == []

    def test_short_secret_returns_empty(self):
        """Secret part < 10 chars returns empty."""
        key = "a" * 30 + "." + "b" * 5  # secret too short
        assert detect_by_format(key) == []

    def test_special_chars_rejected(self):
        """Non-alphanumeric chars in key rejected."""
        key = "a@b.com" * 5 + "." + "b" * 20  # contains @ and .
        assert detect_by_format(key) == []


# ── Class 3: TestScoreProvider (6 tests, pure function) ─────────────────────


class TestScoreProvider:
    """Tests for score_provider() — pure function, no mocks needed."""

    def test_single_signature_match(self):
        """One signature match = 100 points."""
        score = score_provider("openai", "error: visit platform.openai.com for help")
        assert score == 100

    def test_two_signature_matches(self):
        """Two signature matches = 200 points."""
        score = score_provider("anthropic", "request not allowed by anthropic policy")
        assert score == 200  # "request not allowed" + "anthropic"

    def test_no_match_returns_zero(self):
        """No signature match = 0 points."""
        score = score_provider("openai", "some random error message")
        assert score == 0

    def test_429_uses_reduced_weight(self):
        """429 status code uses WEIGHT_RATE_LIMITED=60 instead of 100."""
        score = score_provider("openai", "visit platform.openai.com", status_code=429)
        assert score == 60

    def test_empty_body_returns_zero(self):
        """Empty error body = 0 points."""
        assert score_provider("openai", "") == 0

    def test_case_insensitive_matching(self):
        """Signature matching is case-insensitive."""
        score = score_provider("openai", "visit PLATFORM.OPENAI.COM today")
        assert score == 100


# ── Class 4: TestDetectProviderFlow (12 tests, async with mocks) ────────────


class TestDetectProviderFlow:
    """Tests for detect_provider() — the main async detection flow."""

    # ── Helpers ──────────────────────────────────────────────────────────

    def _make_providers(self, *names):
        """Create a mock PROVIDERS dict with given provider names."""
        providers = {}
        for name in names:
            p = MagicMock()
            p.name = name
            p.base_url = f"https://api.{name}.com"
            p.check_endpoint = "/v1/models"
            p.get_base_url.return_value = p.base_url
            p.build_headers.return_value = {"Authorization": "Bearer test-key"}
            providers[name] = p
        return providers

    def _make_client(
        self,
        post_status=401,
        post_text='{"error":"invalid"}',
        get_status=200,
        get_models=None,
        winning_provider=None,
    ):
        """Create mock client with configurable responses."""
        client = MagicMock()

        async def mock_get(url, headers=None):
            resp = MagicMock()
            resp.status_code = get_status
            if get_status == 200:
                models = get_models or [{"id": "gpt-4o"}]
                resp.json.return_value = {"data": models}
            return resp

        async def mock_post(url, headers=None, json=None):
            resp = MagicMock()
            if winning_provider and winning_provider in url:
                resp.status_code = 200
                resp.text = '{"choices":[]}'
            else:
                resp.status_code = post_status
                resp.text = post_text
            return resp

        client.get = AsyncMock(side_effect=mock_get)
        client.post = AsyncMock(side_effect=mock_post)
        return client

    # ── Tests ────────────────────────────────────────────────────────────

    async def test_suspected_provider_shortcut(self):
        """suspected_provider in PROVIDERS → return immediately, no probing."""
        providers = self._make_providers("openai", "deepseek")
        client = self._make_client()
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test", suspected_provider="openai")
        assert result == "openai"
        client.get.assert_not_called()
        client.post.assert_not_called()

    async def test_suspected_provider_case_insensitive(self):
        """suspected_provider is case-insensitive."""
        providers = self._make_providers("openai")
        client = self._make_client()
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test", suspected_provider="OpenAI")
        assert result == "openai"

    async def test_suspected_provider_unknown_falls_through(self):
        """suspected_provider not in PROVIDERS → falls through to detection."""
        providers = self._make_providers("openai")
        client = self._make_client(winning_provider="openai")
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(
                client, "sk-proj-test123", suspected_provider="nonexistent"
            )
        # Should fall through and detect via prefix (sk-proj- → openai)
        assert result == "openai"

    async def test_format_single_candidate_returns_directly(self):
        """detect_by_format returns 1 candidate in PROVIDERS → return directly."""
        providers = self._make_providers("zhipu")
        client = self._make_client()
        key = "a" * 30 + "." + "b" * 20
        with (
            patch("key_manager.detector.PROVIDERS", providers),
            patch("key_manager.detector.detect_by_format", return_value=["zhipu"]),
        ):
            result = await detect_provider(client, key)
        assert result == "zhipu"

    async def test_format_multiple_candidates_probes(self):
        """detect_by_format returns 2 candidates → probe both, return first 200."""
        providers = self._make_providers("zhipu", "zai")
        client = self._make_client(winning_provider="zai")
        key = "a" * 30 + "." + "b" * 20
        with (
            patch("key_manager.detector.PROVIDERS", providers),
            patch("key_manager.detector.detect_by_format", return_value=["zhipu", "zai"]),
        ):
            result = await detect_provider(client, key)
        assert result == "zai"

    async def test_prefix_single_candidate_returns_directly(self):
        """Unique prefix match → return directly, no probing needed."""
        providers = self._make_providers("openai")
        client = self._make_client()
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-proj-test123456789")
        assert result == "openai"
        # Should NOT have called post (no probing needed)
        client.post.assert_not_called()

    async def test_prefix_multiple_probes(self):
        """Shared prefix → probe all candidates, return first 200."""
        providers = self._make_providers("openai", "deepseek", "together")
        client = self._make_client(winning_provider="deepseek")
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result == "deepseek"

    async def test_concurrent_probe_first_200_wins(self):
        """First provider returning 200 from /chat/completions wins."""
        providers = self._make_providers("openai", "deepseek", "anthropic")
        client = self._make_client(winning_provider="deepseek")
        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result == "deepseek"

    async def test_402_balance_insufficient(self):
        """/v1/models=200 but all /chat/completions=402 → return provider (balance issue)."""
        providers = self._make_providers("openai")
        client = MagicMock()

        async def mock_get(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
            return resp

        async def mock_post(url, headers=None, json=None):
            resp = MagicMock()
            resp.status_code = 402
            resp.text = '{"error":{"message":"balance insufficient"}}'
            return resp

        client.get = AsyncMock(side_effect=mock_get)
        client.post = AsyncMock(side_effect=mock_post)

        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result == "openai"

    async def test_signature_match_above_threshold(self):
        """2+ signatures matched (score >= 200) → return provider."""
        providers = self._make_providers("anthropic")
        client = MagicMock()

        async def mock_get(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"data": [{"id": "claude-3-opus"}]}
            return resp

        async def mock_post(url, headers=None, json=None):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = (
                '{"error":{"message":"request not allowed by anthropic x-api-key"}}'
            )
            return resp

        client.get = AsyncMock(side_effect=mock_get)
        client.post = AsyncMock(side_effect=mock_post)

        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result == "anthropic"

    async def test_signature_match_below_threshold(self):
        """Only 1 signature matched (score=100 < 200) → return None."""
        providers = self._make_providers("openai")
        client = MagicMock()

        async def mock_get(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
            return resp

        async def mock_post(url, headers=None, json=None):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = '{"error":{"message":"visit platform.openai.com"}}'
            return resp

        client.get = AsyncMock(side_effect=mock_get)
        client.post = AsyncMock(side_effect=mock_post)

        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result is None

    async def test_all_timeout_returns_none(self):
        """All requests timeout → return None."""
        providers = self._make_providers("openai", "deepseek")
        client = MagicMock()

        async def mock_get(url, headers=None):
            raise asyncio.TimeoutError()

        async def mock_post(url, headers=None, json=None):
            raise asyncio.TimeoutError()

        client.get = AsyncMock(side_effect=mock_get)
        client.post = AsyncMock(side_effect=mock_post)

        with patch("key_manager.detector.PROVIDERS", providers):
            result = await detect_provider(client, "sk-test123456789")
        assert result is None


# ── Class 5: TestTryProviderHelper (3 tests, async) ─────────────────────────


class TestTryProviderHelper:
    """Tests for _try_provider() and _try_unknown_provider() helper functions."""

    async def test_try_provider_valid(self):
        """Probe returns valid → dict with valid=True."""
        provider = MagicMock()
        provider.probe = AsyncMock(
            return_value=SimpleNamespace(
                valid=True, status_code=200, response_body='{"data":[]}'
            )
        )
        client = MagicMock()
        result = await _try_provider(client, provider, "test-key")
        assert result["valid"] is True
        assert result["status_code"] == 200

    async def test_try_provider_timeout(self):
        """Probe times out → dict with valid=False."""
        provider = MagicMock()
        provider.probe = AsyncMock(side_effect=asyncio.TimeoutError())
        client = MagicMock()
        result = await _try_provider(client, provider, "test-key")
        assert result["valid"] is False

    async def test_try_unknown_provider(self):
        """_try_unknown_provider always returns valid=False."""
        result = await _try_unknown_provider()
        assert result["valid"] is False
        assert result["status_code"] is None
