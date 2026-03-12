"""Webhook notification service for trade execution events.

Manages webhook registrations, dispatches events to matching endpoints,
and tracks delivery status in Redis.
"""

import json
import time
from dataclasses import asdict

from absl import logging

from services.webhook.delivery import deliver
from services.webhook.models import (
    DeliveryRecord,
    DeliveryStatus,
    EventType,
    WebhookEvent,
    WebhookRegistration,
)


class WebhookService:
    """Manages webhook registrations and event dispatch."""

    REGISTRATIONS_KEY = "webhooks:registrations"
    DELIVERIES_KEY = "webhooks:deliveries"
    DELIVERIES_MAX = 5000
    DELIVERIES_TTL = 86400 * 7  # 7 days

    def __init__(self, redis_client):
        self.redis = redis_client

    # ── Registration management ──────────────────────────────────────

    def register(
        self,
        url: str,
        secret: str,
        event_types: list[str] | None = None,
        description: str = "",
    ) -> WebhookRegistration:
        """Register a new webhook endpoint."""
        for et in event_types or []:
            if et not in {e.value for e in EventType}:
                raise ValueError(f"Unknown event type: {et}")

        registration = WebhookRegistration.create(
            url=url,
            secret=secret,
            event_types=event_types or [],
            description=description,
        )
        self.redis.hset(
            self.REGISTRATIONS_KEY,
            registration.webhook_id,
            json.dumps(registration.to_dict(), default=str),
        )
        logging.info("Registered webhook %s -> %s", registration.webhook_id, url)
        return registration

    def unregister(self, webhook_id: str) -> bool:
        """Remove a webhook registration."""
        removed = self.redis.hdel(self.REGISTRATIONS_KEY, webhook_id)
        return removed > 0

    def get_registration(self, webhook_id: str) -> WebhookRegistration | None:
        """Retrieve a single registration by ID."""
        raw = self.redis.hget(self.REGISTRATIONS_KEY, webhook_id)
        if not raw:
            return None
        return self._deserialize_registration(raw)

    def list_registrations(self) -> list[WebhookRegistration]:
        """List all webhook registrations."""
        all_raw = self.redis.hgetall(self.REGISTRATIONS_KEY)
        return [self._deserialize_registration(v) for v in all_raw.values()]

    # ── Event dispatch ───────────────────────────────────────────────

    def dispatch(self, event_type: str, payload: dict) -> list[DeliveryRecord]:
        """Dispatch an event to all matching registered webhooks.

        Returns a list of DeliveryRecords (one per target webhook).
        """
        event = WebhookEvent.create(event_type=event_type, payload=payload)
        registrations = self.list_registrations()
        records = []

        for reg in registrations:
            if not reg.accepts_event(event_type):
                continue
            record = deliver(reg, event)
            self._store_delivery(record)
            records.append(record)

        logging.info(
            "Dispatched event %s (%s) to %d webhooks",
            event.event_id,
            event_type,
            len(records),
        )
        return records

    # ── Delivery tracking ────────────────────────────────────────────

    def get_deliveries(self, count: int = 50, status: str | None = None) -> list[dict]:
        """Return recent delivery records, optionally filtered by status."""
        raw = self.redis.lrange(self.DELIVERIES_KEY, 0, count * 2 - 1)
        results = []
        for item in raw:
            record = json.loads(item)
            if status and record.get("status") != status:
                continue
            results.append(record)
            if len(results) >= count:
                break
        return results

    def get_delivery_stats(self) -> dict:
        """Return summary counts of delivery statuses."""
        records = self.get_deliveries(count=self.DELIVERIES_MAX)
        stats = {"total": len(records), "pending": 0, "delivered": 0, "failed": 0}
        for r in records:
            s = r.get("status", "")
            if s in stats:
                stats[s] += 1
        return stats

    # ── Internals ────────────────────────────────────────────────────

    def _store_delivery(self, record: DeliveryRecord):
        data = json.dumps(record.to_dict(), default=str)
        pipe = self.redis.pipeline()
        pipe.lpush(self.DELIVERIES_KEY, data)
        pipe.ltrim(self.DELIVERIES_KEY, 0, self.DELIVERIES_MAX - 1)
        pipe.expire(self.DELIVERIES_KEY, self.DELIVERIES_TTL)
        pipe.execute()

    @staticmethod
    def _deserialize_registration(raw) -> WebhookRegistration:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return WebhookRegistration(**data)
