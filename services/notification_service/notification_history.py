"""Notification history tracker for delivery status and audit trail."""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field


@dataclass
class NotificationRecord:
    """A single notification delivery attempt."""

    notification_id: str
    signal_id: str
    channel: str
    status: str  # "delivered", "failed", "filtered"
    timestamp: float
    signal_data: dict = field(default_factory=dict)
    error: str = ""


class NotificationHistory:
    """Tracks notification delivery status using Redis.

    Stores notification records in Redis sorted sets keyed by signal
    and maintains a rolling window of recent notifications for monitoring.
    """

    KEY_PREFIX = "notification_history"
    RECENT_KEY = "notification_history:recent"
    MAX_RECENT = 1000
    TTL_SECONDS = 86400 * 7  # 7 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def record_delivery(
        self,
        signal_id: str,
        channel: str,
        success: bool,
        signal_data: dict | None = None,
        error: str = "",
    ) -> NotificationRecord:
        """Record a notification delivery attempt."""
        record = NotificationRecord(
            notification_id=uuid.uuid4().hex[:16],
            signal_id=signal_id,
            channel=channel,
            status="delivered" if success else "failed",
            timestamp=time.time(),
            signal_data=signal_data or {},
            error=error,
        )
        self._store(record)
        return record

    def record_filtered(
        self, signal_id: str, reason: str, signal_data: dict | None = None
    ) -> NotificationRecord:
        """Record a signal that was filtered out."""
        record = NotificationRecord(
            notification_id=uuid.uuid4().hex[:16],
            signal_id=signal_id,
            channel="none",
            status="filtered",
            timestamp=time.time(),
            signal_data=signal_data or {},
            error=reason,
        )
        self._store(record)
        return record

    def get_recent(self, count: int = 50) -> list[dict]:
        """Return the most recent notification records."""
        raw = self.redis.lrange(self.RECENT_KEY, 0, count - 1)
        return [json.loads(r) for r in raw]

    def get_stats(self) -> dict:
        """Return delivery stats from recent history."""
        records = self.get_recent(count=self.MAX_RECENT)
        stats = {"total": len(records), "delivered": 0, "failed": 0, "filtered": 0}
        for r in records:
            status = r.get("status", "")
            if status in stats:
                stats[status] += 1
        return stats

    def _store(self, record: NotificationRecord):
        """Store a notification record in Redis."""
        data = json.dumps(asdict(record), default=str)
        pipe = self.redis.pipeline()
        pipe.lpush(self.RECENT_KEY, data)
        pipe.ltrim(self.RECENT_KEY, 0, self.MAX_RECENT - 1)
        pipe.expire(self.RECENT_KEY, self.TTL_SECONDS)
        pipe.execute()
