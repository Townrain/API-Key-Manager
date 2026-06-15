"""Tests for webhook system."""

import asyncio
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from key_manager.webhook import (
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
    WebhookManager,
)


@pytest.fixture
def manager():
    """Create a fresh WebhookManager instance."""
    return WebhookManager()


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    with patch("httpx.AsyncClient") as mock:
        client = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client


class TestWebhookEvent:
    """Test WebhookEvent enum."""

    def test_all_events_exist(self):
        events = [
            "key.imported",
            "key.checked",
            "key.tested",
            "key.deleted",
            "batch.check.completed",
            "batch.test.completed",
            "error.occurred",
        ]
        for event in events:
            assert WebhookEvent(event).value == event

    def test_event_count(self):
        assert len(WebhookEvent) == 7


class TestWebhookConfig:
    """Test WebhookConfig dataclass."""

    def test_default_values(self):
        config = WebhookConfig(url="https://example.com/hook")
        assert config.url == "https://example.com/hook"
        assert config.events == list(WebhookEvent)
        assert config.secret is None
        assert config.active is True
        assert config.max_retries == 3

    def test_custom_values(self):
        config = WebhookConfig(
            url="https://example.com/hook",
            events=[WebhookEvent.KEY_IMPORTED],
            secret="my-secret",
            active=False,
            max_retries=5,
        )
        assert config.events == [WebhookEvent.KEY_IMPORTED]
        assert config.secret == "my-secret"
        assert config.active is False
        assert config.max_retries == 5


class TestWebhookManager:
    """Test WebhookManager operations."""

    def test_register_webhook(self, manager):
        webhook_id = manager.register("https://example.com/hook")
        assert webhook_id is not None
        assert len(webhook_id) == 16  # secrets.token_hex(8) produces 16 hex chars

        config = manager.get(webhook_id)
        assert config is not None
        assert config.url == "https://example.com/hook"
        assert config.active is True

    def test_register_with_events(self, manager):
        webhook_id = manager.register(
            "https://example.com/hook",
            events=["key.imported", "key.checked"],
        )
        config = manager.get(webhook_id)
        assert WebhookEvent.KEY_IMPORTED in config.events
        assert WebhookEvent.KEY_CHECKED in config.events
        assert WebhookEvent.KEY_TESTED not in config.events

    def test_register_with_secret(self, manager):
        webhook_id = manager.register(
            "https://example.com/hook",
            secret="my-secret",
        )
        config = manager.get(webhook_id)
        assert config.secret == "my-secret"

    def test_unregister_webhook(self, manager):
        webhook_id = manager.register("https://example.com/hook")
        assert manager.get(webhook_id) is not None

        result = manager.unregister(webhook_id)
        assert result is True
        assert manager.get(webhook_id) is None

    def test_unregister_nonexistent(self, manager):
        result = manager.unregister("nonexistent")
        assert result is False

    def test_list_all(self, manager):
        manager.register("https://example.com/hook1")
        manager.register("https://example.com/hook2")

        webhooks = manager.list_all()
        assert len(webhooks) == 2

    def test_update_webhook(self, manager):
        webhook_id = manager.register("https://example.com/hook")

        result = manager.update(webhook_id, active=False, max_retries=5)
        assert result is True

        config = manager.get(webhook_id)
        assert config.active is False
        assert config.max_retries == 5

    def test_update_nonexistent(self, manager):
        result = manager.update("nonexistent", active=False)
        assert result is False

    def test_update_events(self, manager):
        webhook_id = manager.register("https://example.com/hook")

        manager.update(webhook_id, events=["key.imported"])
        config = manager.get(webhook_id)
        assert config.events == [WebhookEvent.KEY_IMPORTED]

    def test_load_from_config(self):
        config = {
            "webhooks": [
                {
                    "url": "https://example.com/hook1",
                    "events": ["key.imported"],
                    "secret": "secret1",
                },
                {
                    "url": "https://example.com/hook2",
                    "active": False,
                },
            ]
        }
        manager = WebhookManager(config)
        webhooks = manager.list_all()
        assert len(webhooks) == 2


class TestWebhookSigning:
    """Test webhook signature generation."""

    def test_sign_payload(self, manager):
        payload = {"event": "key.imported", "data": {"key": "test"}}
        secret = "my-secret"

        signature = manager._sign_payload(payload, secret)

        assert signature.startswith("sha256=")

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        expected = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert signature == f"sha256={expected}"

    def test_sign_different_secrets(self, manager):
        payload = {"event": "key.imported", "data": {}}

        sig1 = manager._sign_payload(payload, "secret1")
        sig2 = manager._sign_payload(payload, "secret2")

        assert sig1 != sig2

    def test_sign_different_payloads(self, manager):
        secret = "my-secret"

        sig1 = manager._sign_payload({"event": "key.imported"}, secret)
        sig2 = manager._sign_payload({"event": "key.checked"}, secret)

        assert sig1 != sig2


class TestWebhookDelivery:
    """Test webhook delivery."""

    @pytest.mark.asyncio
    async def test_dispatch_to_active_webhook(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        manager.register("https://example.com/hook", events=["key.imported"])

        deliveries = await manager.dispatch(
            WebhookEvent.KEY_IMPORTED,
            {"key_masked": "sk-tes...6789", "provider": "openai"},
        )

        assert len(deliveries) == 1
        assert deliveries[0].success is True
        assert deliveries[0].status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_skips_inactive(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        webhook_id = manager.register("https://example.com/hook")
        manager.update(webhook_id, active=False)

        deliveries = await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        assert len(deliveries) == 0

    @pytest.mark.asyncio
    async def test_dispatch_skips_wrong_event(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        manager.register("https://example.com/hook", events=["key.imported"])

        deliveries = await manager.dispatch(WebhookEvent.KEY_CHECKED, {})

        assert len(deliveries) == 0

    @pytest.mark.asyncio
    async def test_dispatch_with_signature(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        manager.register(
            "https://example.com/hook",
            events=["key.imported"],
            secret="my-secret",
        )

        await manager.dispatch(WebhookEvent.KEY_IMPORTED, {"test": True})

        call_kwargs = mock_httpx_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_dispatch_retry_on_failure(self, manager, mock_httpx_client):
        mock_httpx_client.post.side_effect = [
            MagicMock(status_code=500),
            MagicMock(status_code=500),
            MagicMock(status_code=200),
        ]

        manager.register(
            "https://example.com/hook",
            events=["key.imported"],
            max_retries=3,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            deliveries = await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        assert len(deliveries) == 1
        assert deliveries[0].success is True
        assert deliveries[0].attempts == 3

    @pytest.mark.asyncio
    async def test_dispatch_all_retries_fail(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=500)

        manager.register(
            "https://example.com/hook",
            events=["key.imported"],
            max_retries=2,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            deliveries = await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        assert len(deliveries) == 1
        assert deliveries[0].success is False
        assert deliveries[0].attempts == 2

    @pytest.mark.asyncio
    async def test_dispatch_timeout(self, manager, mock_httpx_client):
        import httpx

        mock_httpx_client.post.side_effect = httpx.TimeoutException("timeout")

        manager.register(
            "https://example.com/hook",
            events=["key.imported"],
            max_retries=1,
        )

        deliveries = await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        assert len(deliveries) == 1
        assert deliveries[0].success is False
        assert deliveries[0].error == "Timeout"

    @pytest.mark.asyncio
    async def test_dispatch_multiple_webhooks(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        manager.register("https://example.com/hook1", events=["key.imported"])
        manager.register("https://example.com/hook2", events=["key.imported"])

        deliveries = await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        assert len(deliveries) == 2


class TestDeliveryLog:
    """Test delivery logging."""

    @pytest.mark.asyncio
    async def test_delivery_logged(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)

        manager.register("https://example.com/hook", events=["key.imported"])
        await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        log = manager.get_delivery_log()
        assert len(log) == 1
        assert log[0].success is True

    @pytest.mark.asyncio
    async def test_delivery_log_limit(self, manager, mock_httpx_client):
        mock_httpx_client.post.return_value = MagicMock(status_code=200)
        manager._max_log_size = 5

        manager.register("https://example.com/hook", events=["key.imported"])

        for _ in range(10):
            await manager.dispatch(WebhookEvent.KEY_IMPORTED, {})

        log = manager.get_delivery_log()
        assert len(log) == 5

    def test_clear_delivery_log(self, manager):
        manager._delivery_log = [
            WebhookDelivery(
                webhook_url="https://example.com",
                event=WebhookEvent.KEY_IMPORTED,
                payload={},
            )
        ]

        manager.clear_delivery_log()
        assert len(manager.get_delivery_log()) == 0

    def test_get_delivery_log_limit(self, manager):
        for i in range(100):
            manager._delivery_log.append(
                WebhookDelivery(
                    webhook_url=f"https://example.com/{i}",
                    event=WebhookEvent.KEY_IMPORTED,
                    payload={},
                )
            )

        log = manager.get_delivery_log(limit=10)
        assert len(log) == 10
