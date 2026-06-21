"""Tests for DeepSeek balance checking functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from key_manager.providers.deepseek import DeepSeekProvider
from key_manager.providers.base import BalanceResult


class TestDeepSeekBalance:
    """Test DeepSeek get_balance implementation."""

    async def test_get_balance_success(self):
        """Test successful balance retrieval."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        # Mock successful balance response
        balance_response = MagicMock()
        balance_response.status_code = 200
        balance_response.json.return_value = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "110.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "100.00"
                }
            ]
        }
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.balance == 110.00
        assert result.currency == "CNY"
        assert result.error is None
        assert result.raw is not None

        # Verify correct API endpoint was called
        mock_client.get.assert_called_once_with(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": "Bearer test-key"}
        )

    async def test_get_balance_usd_currency(self):
        """Test balance with USD currency."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 200
        balance_response.json.return_value = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "USD",
                    "total_balance": "50.00",
                    "granted_balance": "5.00",
                    "topped_up_balance": "45.00"
                }
            ]
        }
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.balance == 50.00
        assert result.currency == "USD"

    async def test_get_balance_multiple_currencies(self):
        """Test balance with multiple currencies (uses first one)."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 200
        balance_response.json.return_value = {
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "100.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "90.00"
                },
                {
                    "currency": "USD",
                    "total_balance": "20.00",
                    "granted_balance": "2.00",
                    "topped_up_balance": "18.00"
                }
            ]
        }
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        # Should use first balance info
        assert result.supported is True
        assert result.balance == 100.00
        assert result.currency == "CNY"

    async def test_get_balance_empty_balance_infos(self):
        """Test balance with empty balance_infos array."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 200
        balance_response.json.return_value = {
            "is_available": False,
            "balance_infos": []
        }
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.balance == 0.0
        assert result.error is None

    async def test_get_balance_invalid_key(self):
        """Test balance with invalid API key."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 401
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "invalid-key")

        assert result.supported is True
        assert result.error == "invalid key or forbidden"

    async def test_get_balance_forbidden(self):
        """Test balance with forbidden access."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 403
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "forbidden-key")

        assert result.supported is True
        assert result.error == "invalid key or forbidden"

    async def test_get_balance_server_error(self):
        """Test balance with server error."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 500
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.error == "status 500"

    async def test_get_balance_network_error(self):
        """Test balance with network error."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        mock_client.get.side_effect = Exception("Network timeout")

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.error == "Network timeout"

    async def test_get_balance_zero_balance(self):
        """Test balance with zero balance."""
        provider = DeepSeekProvider()
        mock_client = AsyncMock()

        balance_response = MagicMock()
        balance_response.status_code = 200
        balance_response.json.return_value = {
            "is_available": False,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "0.00",
                    "granted_balance": "0.00",
                    "topped_up_balance": "0.00"
                }
            ]
        }
        mock_client.get.return_value = balance_response

        result = await provider.get_balance(mock_client, "test-key")

        assert result.supported is True
        assert result.balance == 0.00
        assert result.currency == "CNY"
