"""Tests for three-step check logic in base.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.providers.base import ProviderBase, CheckResult
from tests.helpers import MockProvider

class TestThreeStepCheck:
    """Tests for three-step check logic."""

    async def test_step1_get_models_from_api(self):
        """Step 1: GET /v1/models returns model list."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock /v1/models response
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [
                {"id": "model-1"},
                {"id": "model-2"},
                {"id": "model-3"},
            ]
        }
        mock_client.get.return_value = models_response

        # Mock chat completions response
        chat_response = MagicMock()
        chat_response.status_code = 200
        mock_client.post.return_value = chat_response

        result = await provider.check(mock_client, "test-key")

        # Should call /v1/models first
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/models" in call_args[0][0]

        # Should return valid
        assert result.valid is True

    async def test_step2_serial_when_less_than_10_models(self):
        """Step 2: < 10 models → serial test."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock /v1/models with 5 models
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [{"id": f"model-{i}"} for i in range(5)]
        }
        mock_client.get.return_value = models_response

        # Mock chat completions - first 2 fail, third succeeds
        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count <= 2:
                resp.status_code = 401
                resp.text = "unauthorized"
                resp.json.return_value = {"error": {"message": "invalid key"}}
            else:
                resp.status_code = 200
            return resp

        mock_client.post = mock_post

        result = await provider.check(mock_client, "test-key")

        # Should return valid (third model succeeded)
        assert result.valid is True
        assert result.status_code == 200
        # Should have called post 3 times (serial)
        assert call_count == 3

    async def test_step3_parallel_when_10_or_more_models(self):
        """Step 3: >= 10 models → parallel test with batch_size=10."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock /v1/models with 15 models
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [{"id": f"model-{i}"} for i in range(15)]
        }
        mock_client.get.return_value = models_response

        # Track which models are called
        called_models = []

        async def mock_post(*args, **kwargs):
            model = kwargs.get("json", {}).get("model", "")
            called_models.append(model)
            resp = MagicMock()
            # model-10 succeeds (second batch)
            if model == "model-10":
                resp.status_code = 200
            else:
                resp.status_code = 401
                resp.text = "unauthorized"
                resp.json.return_value = {"error": {"message": "invalid key"}}
            return resp

        mock_client.post = mock_post

        result = await provider.check(mock_client, "test-key")

        # Should return valid (model-10 succeeded)
        assert result.valid is True
        # Should have tried models from both batches
        assert len(called_models) >= 10
    async def test_skip_models_endpoint_for_replicate(self):
        """Skip /v1/models for providers like replicate that don't support it."""
        # Simulate provider where check_endpoint is not a models endpoint
        provider = MockProvider()
        provider.check_endpoint = "/v1/account"  # Not a models endpoint

        mock_client = AsyncMock()

        # Mock chat completions response
        chat_response = MagicMock()
        chat_response.status_code = 200
        mock_client.post.return_value = chat_response

        result = await provider.check(mock_client, "test-key")

        # Should NOT call GET (skip models endpoint)
        mock_client.get.assert_not_called()

        # Should return error because no models available
        assert result.valid is False
        assert "no models available" in result.error

    async def test_retry_failed_models(self):
        """Failed models should be retried."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock /v1/models with 3 models
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [{"id": "model-1"}, {"id": "model-2"}, {"id": "model-3"}]
        }
        mock_client.get.return_value = models_response

        # Track which models are called
        called_models = []
        async def mock_post(*args, **kwargs):
            model = kwargs.get("json", {}).get("model", "")
            called_models.append(model)
            resp = MagicMock()
            # model-1 fails, model-2 succeeds, model-3 fails
            if model == "model-1":
                resp.status_code = 401
                resp.text = "unauthorized"
                resp.json.return_value = {"error": {"message": "invalid key"}}
            elif model == "model-2":
                resp.status_code = 200
            else:
                resp.status_code = 401
                resp.text = "unauthorized"
                resp.json.return_value = {"error": {"message": "invalid key"}}
            return resp

        mock_client.post = mock_post

        result = await provider.check(mock_client, "test-key")

        # Should return valid (model-2 succeeded)
        assert result.valid is True
        # Should have tried 2 models (stopped at first success)
        assert len(called_models) == 2

    async def test_all_models_fail(self):
        """All models fail returns invalid."""
        provider = MockProvider()
        mock_client = AsyncMock()

        # Mock /v1/models with 3 models
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [{"id": "model-1"}, {"id": "model-2"}, {"id": "model-3"}]
        }
        mock_client.get.return_value = models_response

        # All models fail
        async def mock_post(*args, **kwargs):
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "unauthorized"
            resp.json.return_value = {"error": {"message": "invalid key"}}
            return resp

        mock_client.post = mock_post

        result = await provider.check(mock_client, "test-key")

        # Should return invalid
        assert result.valid is False
        assert result.status_code == 401

    async def test_use_check_endpoint_not_hardcoded(self):
        """Should use self.check_endpoint, not hardcoded /v1/models."""
        provider = MockProvider()
        provider.check_endpoint = "/custom/models/path"

        mock_client = AsyncMock()

        # Mock response
        models_response = MagicMock()
        models_response.status_code = 200
        models_response.json.return_value = {"data": [{"id": "model-1"}]}
        mock_client.get.return_value = models_response

        chat_response = MagicMock()
        chat_response.status_code = 200
        mock_client.post.return_value = chat_response

        await provider.check(mock_client, "test-key")

        # Should use custom check_endpoint
        call_args = mock_client.get.call_args
        assert "/custom/models/path" in call_args[0][0]
