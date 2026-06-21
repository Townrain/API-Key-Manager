"""Tests for improved token limit testing (fast method)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from key_manager.providers.base import ProviderBase, TestResult


class MockProvider(ProviderBase):
    name = "test"
    base_url = "https://api.test.com/v1"
    check_endpoint = "/models"
    check_model = "test-model"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def test_token_limit(self, client, key, models=None):
        """Mock implementation of test_token_limit."""
        import re
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        
        large_tokens = 1000000
        
        try:
            resp = await client.post(
                f"{self.get_base_url()}/chat/completions",
                headers=headers,
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": large_tokens
                }
            )
            
            if resp.status_code == 200:
                return TestResult(max_tokens=large_tokens)
            
            # Parse error to extract limit
            try:
                error_data = resp.json()
                error_msg = error_data.get("error", {}).get("message", "")
                
                # Try to find limit after 'maximum' or 'max' keyword
                max_match = re.search(r'(?:maximum|max)\s+(?:is\s+)?(\d+)', error_msg, re.IGNORECASE)
                if max_match:
                    limit = int(max_match.group(1))
                    if limit >= 100:
                        return TestResult(max_tokens=limit)
                
                # Fallback: find numbers and use the second largest
                numbers = re.findall(r'\d+', error_msg)
                if len(numbers) >= 2:
                    sorted_nums = sorted(set(int(n) for n in numbers), reverse=True)
                    for num in sorted_nums:
                        if num >= 100:
                            return TestResult(max_tokens=num)
                elif numbers:
                    num = int(numbers[0])
                    if num >= 100:
                        return TestResult(max_tokens=num)
            except Exception:
                pass
            
            return TestResult(max_tokens=None, error=error_msg)
        except Exception as e:
            return TestResult(max_tokens=None, error=str(e))

    async def test_concurrency(self, client, key, models=None):
        """Mock implementation of test_concurrency."""
        return TestResult(max_concurrency=10, error=None)

class TestTokenLimitFast:
    """Test the new fast token limit detection method."""

    async def test_parse_limit_from_error_message(self):
        """Should parse token limit from error message."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock error response with limit info
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.json.return_value = {
            "error": {
                "message": "max_tokens is too large: 1000000. The maximum is 16384.",
                "type": "invalid_request_error"
            }
        }
        mock_client.post.return_value = error_response

        result = await provider.test_token_limit(mock_client, "test-key", [])

        assert result.max_tokens == 16384
        assert result.error is None

    async def test_parse_limit_from_different_format(self):
        """Should parse limit from different error formats."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Test different error message formats
        test_cases = [
            ("max_tokens must be less than or equal to 8192", 8192),
            ("This model's maximum context length is 32768 tokens", 32768),
            ("Token limit exceeded. Max: 4096", 4096),
        ]

        for error_msg, expected_limit in test_cases:
            error_response = MagicMock()
            error_response.status_code = 400
            error_response.json.return_value = {
                "error": {"message": error_msg}
            }
            mock_client.post.return_value = error_response

            result = await provider.test_token_limit(mock_client, "test-key", [])
            assert result.max_tokens == expected_limit, f"Failed for: {error_msg}"

    async def test_success_with_large_value(self):
        """Should return large value if request succeeds."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock success response
        success_response = MagicMock()
        success_response.status_code = 200
        mock_client.post.return_value = success_response

        result = await provider.test_token_limit(mock_client, "test-key", [])

        assert result.max_tokens == 1000000

    async def test_network_error(self):
        """Should handle network errors gracefully."""
        provider = MockProvider()
        mock_client = AsyncMock()

        mock_client.post.side_effect = Exception("Connection timeout")

        result = await provider.test_token_limit(mock_client, "test-key", [])

        assert result.max_tokens is None
        assert "Connection timeout" in result.error

    async def test_no_numbers_in_error(self):
        """Should handle errors without numbers."""
        provider = MockProvider()
        mock_client = AsyncMock()

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.json.return_value = {
            "error": {"message": "Invalid request"}
        }
        mock_client.post.return_value = error_response

        result = await provider.test_token_limit(mock_client, "test-key", [])

        assert result.max_tokens is None
        assert result.error is not None
