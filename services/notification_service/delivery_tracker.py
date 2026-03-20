"""Enhanced delivery tracking with per-channel status and metrics."""

import json
import time
from dataclasses import asdict, dataclass, field


@dataclass
class DeliveryReceipt:
    """A delivery receipt for a signal sent to a specific channel."""

    receipt_id: str
    signal_id: str
    user_id: str
    channel: str
    status: str  # pending, sent, delivered, failed, skipped
    timestamp: float
    error: str = ""
    skipped_reason: str = ""
    latency_ms: float = 0.0


class DeliveryTracker:
    """Tracks delivery status across all channels with metrics.

    Provides per-channel and per-user delivery metrics, plus a dead-letter
    queue for failed deliveries that need manual review or retry.
    """

    RECEIPT_PREFIX = "delivery:receipt"
    METRICS_PREFIX = "delivery:metrics"
    DLQ_KEY = "delivery:dlq"
    MAX_DLQ = 10000
    TTL_SECONDS = 86400 * 30  # 30 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def record(self, receipt: DeliveryReceipt):
        """Record a delivery receipt and update metrics."""
        data = json.dumps(asdict(receipt), default=str)

        # Store receipt
        receipt_key = f"{self.RECEIPT_PREFIX}:{receipt.signal_id}:{receipt.channel}"
        pipe = self.redis.pipeline()
        pipe.setex(receipt_key, self.TTL_SECONDS, data)

        # Update channel metrics
        metrics_key = f"{self.METRICS_PREFIX}:{receipt.channel}"
        pipe.hincrby(metrics_key, "total", 1)
        pipe.hincrby(metrics_key, receipt.status, 1)
        if receipt.latency_ms > 0:
            pipe.hincrbyfloat(metrics_key, "total_latency_ms", receipt.latency_ms)

        # Dead-letter queue for failures
        if receipt.status == "failed":
            pipe.lpush(self.DLQ_KEY, data)
            pipe.ltrim(self.DLQ_KEY, 0, self.MAX_DLQ - 1)

        pipe.execute()

    def get_channel_metrics(self, channel: str) -> dict:
        """Return delivery metrics for a channel."""
        key = f"{self.METRICS_PREFIX}:{channel}"
        raw = self.redis.hgetall(key)
        if not raw:
            return {"total": 0, "delivered": 0, "failed": 0, "skipped": 0}

        total = int(raw.get("total", 0))
        delivered = int(raw.get("delivered", 0))
        failed = int(raw.get("failed", 0))
        skipped = int(raw.get("skipped", 0))
        total_latency = float(raw.get("total_latency_ms", 0))
        avg_latency = total_latency / max(delivered, 1)

        return {
            "total": total,
            "delivered": delivered,
            "failed": failed,
            "skipped": skipped,
            "avg_latency_ms": round(avg_latency, 2),
        }

    def get_dlq(self, count: int = 50) -> list[dict]:
        """Return recent dead-letter queue entries."""
        raw = self.redis.lrange(self.DLQ_KEY, 0, count - 1)
        return [json.loads(r) for r in raw]

    def get_receipt(self, signal_id: str, channel: str) -> dict | None:
        """Look up a specific delivery receipt."""
        key = f"{self.RECEIPT_PREFIX}:{signal_id}:{channel}"
        raw = self.redis.get(key)
        if raw:
            return json.loads(raw)
        return None
