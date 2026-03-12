"""Data models for the webhook notification service."""

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum


class EventType(str, Enum):
    """Supported webhook event types."""

    TRADE_EXECUTED = "trade.executed"
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_UPDATED = "position.updated"
    ALERT_TRIGGERED = "alert.triggered"
    SIGNAL_GENERATED = "signal.generated"


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class WebhookRegistration:
    """A registered webhook endpoint."""

    webhook_id: str
    url: str
    secret: str
    event_types: list[str]
    active: bool = True
    created_at: float = field(default_factory=time.time)
    description: str = ""

    @staticmethod
    def create(
        url: str,
        secret: str,
        event_types: list[str],
        description: str = "",
    ) -> "WebhookRegistration":
        return WebhookRegistration(
            webhook_id=uuid.uuid4().hex[:16],
            url=url,
            secret=secret,
            event_types=event_types,
            description=description,
        )

    def accepts_event(self, event_type: str) -> bool:
        """Check if this webhook is subscribed to the given event type."""
        if not self.active:
            return False
        if not self.event_types:
            return True
        return event_type in self.event_types

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WebhookEvent:
    """An event to be delivered via webhook."""

    event_id: str
    event_type: str
    payload: dict
    timestamp: float = field(default_factory=time.time)

    @staticmethod
    def create(event_type: str, payload: dict) -> "WebhookEvent":
        return WebhookEvent(
            event_id=uuid.uuid4().hex[:16],
            event_type=event_type,
            payload=payload,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DeliveryRecord:
    """Tracks a single webhook delivery attempt."""

    delivery_id: str
    webhook_id: str
    event_id: str
    event_type: str
    status: str
    attempt: int
    max_attempts: int
    created_at: float
    completed_at: float = 0.0
    status_code: int = 0
    error: str = ""

    @staticmethod
    def create(
        webhook_id: str,
        event_id: str,
        event_type: str,
        max_attempts: int = 3,
    ) -> "DeliveryRecord":
        return DeliveryRecord(
            delivery_id=uuid.uuid4().hex[:16],
            webhook_id=webhook_id,
            event_id=event_id,
            event_type=event_type,
            status=DeliveryStatus.PENDING.value,
            attempt=0,
            max_attempts=max_attempts,
            created_at=time.time(),
        )

    def mark_delivered(self, status_code: int):
        self.status = DeliveryStatus.DELIVERED.value
        self.status_code = status_code
        self.completed_at = time.time()

    def mark_failed(self, error: str, status_code: int = 0):
        self.status = DeliveryStatus.FAILED.value
        self.error = error
        self.status_code = status_code
        self.completed_at = time.time()

    def to_dict(self) -> dict:
        return asdict(self)
