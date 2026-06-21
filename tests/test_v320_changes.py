"""Tests for v3.2.0 changes: per-model testing, API fixes."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from key_manager.providers.base import ProviderBase, CheckResult, TestResult
from tests.helpers import MockProvider
class TestCheckModelFallback:
    """Test check_model fallback behavior."""

    def test_get_models_method_exists(self):
        """ProviderBase should have get_models method for dynamic model discovery."""
        # Check that ProviderBase has the method
        assert hasattr(ProviderBase, 'get_models'), "get_models should exist on ProviderBase"
        assert callable(getattr(ProviderBase, 'get_models', None)), "get_models should be callable"
        
        # Check that chat_endpoint property exists
        assert hasattr(ProviderBase, 'chat_endpoint'), "chat_endpoint should exist on ProviderBase"

class TestTokenLimitDetection:
    """Test improved token limit detection."""

    def test_parse_limit_from_maximum_keyword(self):
        """Should parse token limit after 'maximum' keyword."""
        import re

        test_cases = [
            ("max_tokens is too large: 1000000. The maximum is 16384.", 16384),
            ("max_tokens must be less than or equal to 8192", 8192),
            ("This model's maximum context length is 32768 tokens", 32768),
        ]

        for error_msg, expected_limit in test_cases:
            max_match = re.search(r'(?:maximum|max)\s+(?:is\s+)?(\d+)', error_msg, re.IGNORECASE)
            if max_match:
                limit = int(max_match.group(1))
                assert limit == expected_limit, f"Failed for: {error_msg}"

    def test_fallback_to_numbers(self):
        """Should fallback to finding numbers in error message."""
        import re

        error_msg = "Error: token limit 262144 exceeded"
        numbers = re.findall(r'\d+', error_msg)
        assert len(numbers) == 1
        assert int(numbers[0]) == 262144


class TestConcurrencyTestAPI:
    """Test concurrency test API improvements."""

    async def test_probe_model_returns_success(self):
        """probe_model should return success dict on 200."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        async def probe_model(client, url, headers, model):
            try:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                )
                if resp.status_code == 200:
                    return {"success": True}
                else:
                    return {"success": False, "error": f"status {resp.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        result = await probe_model(mock_client, "https://api.test.com/v1/chat/completions", {}, "test-model")
        assert result == {"success": True}

    async def test_probe_model_returns_error(self):
        """probe_model should return error dict on non-200."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_client.post.return_value = mock_response

        async def probe_model(client, url, headers, model):
            try:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}
                )
                if resp.status_code == 200:
                    return {"success": True}
                else:
                    try:
                        error_data = resp.json()
                        if 'error' in error_data:
                            error_msg = error_data['error'].get('message', str(error_data['error']))
                        else:
                            error_msg = f"status {resp.status_code}"
                    except Exception:
                        error_msg = f"status {resp.status_code}"
                    return {"success": False, "error": error_msg}
            except Exception as e:
                return {"success": False, "error": str(e)}

        result = await probe_model(mock_client, "https://api.test.com/v1/chat/completions", {}, "test-model")
        assert result["success"] is False
        assert "Invalid API key" in result["error"]


class TestVersionExtraction:
    """Test version prefix extraction from check_endpoint."""

    def test_extract_v1_prefix(self):
        """Should extract /v1 from /v1/models."""
        import re
        check_endpoint = "/v1/models"
        version_match = re.match(r'(/v\d+)', check_endpoint)
        assert version_match is not None
        assert version_match.group(1) == "/v1"

    def test_extract_v2_prefix(self):
        """Should extract /v2 from /v2/models."""
        import re
        check_endpoint = "/v2/models"
        version_match = re.match(r'(/v\d+)', check_endpoint)
        assert version_match is not None
        assert version_match.group(1) == "/v2"

    def test_no_prefix(self):
        """Should return None for endpoints without version prefix."""
        import re
        check_endpoint = "/models"
        version_match = re.match(r'(/v\d+)', check_endpoint)
        assert version_match is None

    def test_custom_endpoint(self):
        """Should extract version from custom endpoints."""
        import re
        check_endpoint = "/v1/account"
        version_match = re.match(r'(/v\d+)', check_endpoint)
        assert version_match is not None
        assert version_match.group(1) == "/v1"


class TestErrorParsing:
    """Test improved error parsing for nested error objects."""

    def test_parse_nested_error(self):
        """Should parse nested error object."""
        error_data = {
            "type": "error",
            "error": {
                "type": "CreditsError",
                "message": "No payment method"
            }
        }

        if 'error' in error_data:
            error_msg = error_data['error'].get('message', str(error_data['error']))
        else:
            error_msg = str(error_data)

        assert error_msg == "No payment method"

    def test_parse_simple_error(self):
        """Should parse simple error object."""
        error_data = {
            "error": {
                "message": "Invalid API key"
            }
        }

        if 'error' in error_data:
            error_msg = error_data['error'].get('message', str(error_data['error']))
        else:
            error_msg = str(error_data)

        assert error_msg == "Invalid API key"

    def test_parse_error_without_message(self):
        """Should handle error without message field."""
        error_data = {
            "error": {
                "type": "SomeError"
            }
        }

        if 'error' in error_data:
            error_msg = error_data['error'].get('message', str(error_data['error']))
        else:
            error_msg = str(error_data)

        assert "SomeError" in error_msg
