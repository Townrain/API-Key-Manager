"""
Webhook system for API Key Manager.

Supports:
- Multiple event types
- Retry logic with exponential backoff
- HMAC-SHA256 signature verification
- Async HTTP delivery
"""

import asyncio
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import httpx


class WebhookEvent(str, Enum):
    """Supported webhook event types."""
    KEY_IMPORTED = "key.imported"
    KEY_CHECKED = "key.checked"
    KEY_TESTED = "key.tested"
    KEY_DELETED = "key.deleted"
    BATCH_CHECK_COMPLETED = "batch.check.completed"
    BATCH_TEST_COMPLETED = "batch.test.completed"
    ERROR_OCCURRED = "error.occurred"


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    url: str
    events: list[WebhookEvent] = field(default_factory=lambda: list(WebhookEvent))
    secret: str | None = None
    active: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 10.0


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""
    webhook_url: str
    event: WebhookEvent
    payload: dict
    status_code: int | None = None
    success: bool = False
    error: str | None = None
    attempts: int = 0
    delivered_at: str | None = None


class WebhookManager:
    """Manages webhook registrations and deliveries."""

    def __init__(self, config: dict | None = None):
        self._webhooks: dict[str, WebhookConfig] = {}
        self._delivery_log: list[WebhookDelivery] = []
        self._max_log_size = 1000
        self._config = config or {}
        self._load_from_config()

    def _load_from_config(self):
        """Load webhooks from configuration."""
        webhooks = self._config.get("webhooks", [])
        for wh in webhooks:
            if wh.get("url"):
                self.register(
                    url=wh["url"],
                    events=wh.get("events", [e.value for e in WebhookEvent]),
                    secret=wh.get("secret"),
                    active=wh.get("active", True),
                    max_retries=wh.get("max_retries", 3),
                )

    def register(
        self,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
        active: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Register a new webhook."""
        webhook_id = secrets.token_hex(8)  # 16 hex chars = 64 bits of randomness

        event_list = []
        if events:
            for e in events:
                try:
                    event_list.append(WebhookEvent(e))
                except ValueError:
                    pass
        else:
            event_list = list(WebhookEvent)

        self._webhooks[webhook_id] = WebhookConfig(
            url=url,
            events=event_list,
            secret=secret,
            active=active,
            max_retries=max_retries,
        )

        return webhook_id

    def unregister(self, webhook_id: str) -> bool:
        """Unregister a webhook."""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            return True
        return False

    def get(self, webhook_id: str) -> WebhookConfig | None:
        """Get webhook configuration."""
        return self._webhooks.get(webhook_id)

    def list_all(self) -> dict[str, WebhookConfig]:
        """List all registered webhooks."""
        return dict(self._webhooks)

    def update(self, webhook_id: str, **kwargs) -> bool:
        """Update webhook configuration."""
        wh = self._webhooks.get(webhook_id)
        if not wh:
            return False

        for key, value in kwargs.items():
            if hasattr(wh, key):
                if key == "events" and isinstance(value, list):
                    event_list = []
                    for e in value:
                        try:
                            event_list.append(WebhookEvent(e) if isinstance(e, str) else e)
                        except ValueError:
                            pass
                    setattr(wh, key, event_list)
                else:
                    setattr(wh, key, value)

        return True

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    async def dispatch(self, event: WebhookEvent, data: dict) -> list[WebhookDelivery]:
        """Dispatch an event to all registered webhooks."""
        deliveries = []

        payload = {
            "event": event.value,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "data": data,
        }

        tasks = []
        for _webhook_id, config in self._webhooks.items():
            if not config.active:
                continue
            if event not in config.events:
                continue
            tasks.append(self._deliver(config, payload))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, WebhookDelivery):
                    deliveries.append(result)
                    self._log_delivery(result)

        return deliveries

    async def _deliver(self, config: WebhookConfig, payload: dict) -> WebhookDelivery:
        """Deliver a webhook with retry logic."""
        delivery = WebhookDelivery(
            webhook_url=config.url,
            event=WebhookEvent(payload["event"]),
            payload=payload,
        )

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "API-Key-Manager/1.0",
            "X-Webhook-Event": payload["event"],
            "X-Webhook-Timestamp": payload["timestamp"],
        }

        if config.secret:
            headers["X-Webhook-Signature"] = self._sign_payload(payload, config.secret)

        last_error = None
        for attempt in range(config.max_retries):
            delivery.attempts = attempt + 1

            try:
                async with httpx.AsyncClient(timeout=config.timeout) as client:
                    response = await client.post(
                        config.url,
                        json=payload,
                        headers=headers,
                    )

                    delivery.status_code = response.status_code

                    if 200 <= response.status_code < 300:
                        delivery.success = True
                        delivery.delivered_at = datetime.now(timezone.utc).isoformat() + "Z"
                        return delivery

                    last_error = f"HTTP {response.status_code}"

            except httpx.TimeoutException:
                last_error = "Timeout"
            except httpx.ConnectError:
                last_error = "Connection error"
            except Exception as e:
                last_error = str(e)

            if attempt < config.max_retries - 1:
                delay = config.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        delivery.error = last_error
        delivery.delivered_at = datetime.now(timezone.utc).isoformat() + "Z"
        return delivery

    def _log_delivery(self, delivery: WebhookDelivery):
        """Log a delivery attempt."""
        self._delivery_log.append(delivery)
        if len(self._delivery_log) > self._max_log_size:
            self._delivery_log = self._delivery_log[-self._max_log_size:]

    def get_delivery_log(self, limit: int = 50) -> list[WebhookDelivery]:
        """Get recent delivery log."""
        return self._delivery_log[-limit:]

    def clear_delivery_log(self):
        """Clear delivery log."""
        self._delivery_log.clear()


# Global webhook manager instance
webhook_manager = WebhookManager()
