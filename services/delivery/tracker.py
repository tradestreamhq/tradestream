"""Delivery status tracking across all channels."""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class DeliveryReceipt:
    """Tracks the delivery status of a signal to a user on a channel."""

    receipt_id: str
    signal_id: str
    user_id: str
    channel: str
    status: str  # pending, sent, delivered, read, failed
    external_message_id: str = ""
    error_message: str = ""
    retry_count: int = 0
    created_at: float = 0.0
    sent_at: float = 0.0
    delivered_at: float = 0.0


class DeliveryTracker:
    """Tracks delivery receipts in Redis.

    Stores per-signal, per-user, per-channel delivery status.
    Supports querying delivery stats and recent deliveries.
    """

    KEY_PREFIX = "delivery:receipt"
    RECENT_KEY = "delivery:recent"
    STATS_KEY = "delivery:stats"
    MAX_RECENT = 1000
    TTL_SECONDS = 86400 * 7  # 7 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def create_receipt(
        self, signal_id: str, user_id: str, channel: str
    ) -> DeliveryReceipt:
        """Create a pending delivery receipt."""
        receipt = DeliveryReceipt(
            receipt_id=uuid.uuid4().hex[:16],
            signal_id=signal_id,
            user_id=user_id,
            channel=channel,
            status="pending",
            created_at=time.time(),
        )
        self._store(receipt)
        self._increment_stat(channel, "pending")
        return receipt

    def mark_sent(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        external_id: str = "",
    ) -> None:
        """Mark a delivery as sent."""
        receipt = self._load(signal_id, user_id, channel)
        if receipt:
            receipt.status = "sent"
            receipt.external_message_id = external_id
            receipt.sent_at = time.time()
            self._store(receipt)
            self._increment_stat(channel, "sent")

    def mark_failed(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        error: str,
        retry_count: int = 0,
    ) -> None:
        """Mark a delivery as failed."""
        receipt = self._load(signal_id, user_id, channel)
        if receipt:
            receipt.status = "failed"
            receipt.error_message = error
            receipt.retry_count = retry_count
            self._store(receipt)
            self._increment_stat(channel, "failed")

    def get_delivery_stats(self, days: int = 7) -> dict:
        """Get aggregate delivery statistics."""
        raw = self.redis.hgetall(self.STATS_KEY)
        stats = {}
        for key, value in raw.items():
            if isinstance(key, bytes):
                key = key.decode()
            if isinstance(value, bytes):
                value = value.decode()
            channel, status = key.rsplit(":", 1)
            if channel not in stats:
                stats[channel] = {}
            stats[channel][status] = int(value)
        return stats

    def get_recent(self, count: int = 50) -> list[dict]:
        """Get recent delivery receipts."""
        raw = self.redis.lrange(self.RECENT_KEY, 0, count - 1)
        return [json.loads(r) for r in raw]

    def _store(self, receipt: DeliveryReceipt) -> None:
        """Store receipt in Redis."""
        key = (
            f"{self.KEY_PREFIX}:{receipt.signal_id}:{receipt.user_id}:{receipt.channel}"
        )
        data = json.dumps(asdict(receipt), default=str)
        pipe = self.redis.pipeline()
        pipe.setex(key, self.TTL_SECONDS, data)
        pipe.lpush(self.RECENT_KEY, data)
        pipe.ltrim(self.RECENT_KEY, 0, self.MAX_RECENT - 1)
        pipe.expire(self.RECENT_KEY, self.TTL_SECONDS)
        pipe.execute()

    def _load(
        self, signal_id: str, user_id: str, channel: str
    ) -> Optional[DeliveryReceipt]:
        """Load a receipt from Redis."""
        key = f"{self.KEY_PREFIX}:{signal_id}:{user_id}:{channel}"
        raw = self.redis.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        return DeliveryReceipt(**data)

    def _increment_stat(self, channel: str, status: str) -> None:
        """Increment aggregate delivery stat counter."""
        self.redis.hincrby(self.STATS_KEY, f"{channel}:{status}", 1)
