"""Dead letter queue for failed signal deliveries.

Stores failed delivery attempts in Redis with retry metadata.
Supports configurable max retries with exponential backoff.
"""

import json
import logging
import time

logger = logging.getLogger(__name__)

DLQ_KEY = "signal_pipeline:dlq"
DLQ_PROCESSING_KEY = "signal_pipeline:dlq:processing"


class DeadLetterQueue:
    """Redis-backed dead letter queue for failed signal deliveries.

    Usage:
        dlq = DeadLetterQueue(redis_client, max_retries=3)
        dlq.enqueue(signal_payload, subscriber_id, channel, endpoint, error="timeout")

        # In a retry worker:
        items = dlq.dequeue_batch(10)
        for item in items:
            if try_deliver(item):
                dlq.ack(item["dlq_id"])
            else:
                dlq.nack(item["dlq_id"])
    """

    def __init__(self, redis_client, max_retries: int = 3, base_delay: float = 30.0):
        self.redis = redis_client
        self.max_retries = max_retries
        self.base_delay = base_delay

    def enqueue(
        self,
        signal: dict,
        subscriber_id: str,
        channel: str,
        endpoint: str,
        error: str = "",
    ) -> str:
        """Add a failed delivery to the dead letter queue.

        Returns the DLQ entry ID.
        """
        dlq_id = f"dlq:{subscriber_id}:{int(time.time() * 1000)}"
        entry = {
            "dlq_id": dlq_id,
            "signal": signal,
            "subscriber_id": subscriber_id,
            "channel": channel,
            "endpoint": endpoint,
            "error": error,
            "retry_count": 0,
            "max_retries": self.max_retries,
            "created_at": time.time(),
            "next_retry_at": time.time() + self.base_delay,
        }
        self.redis.lpush(DLQ_KEY, json.dumps(entry, default=str))
        logger.info(
            "DLQ enqueued: subscriber=%s channel=%s error=%s",
            subscriber_id,
            channel,
            error,
        )
        return dlq_id

    def dequeue_batch(self, batch_size: int = 10) -> list:
        """Dequeue up to batch_size items that are ready for retry.

        Items are moved to a processing set to prevent double-processing.
        """
        now = time.time()
        items = []
        checked = 0
        max_check = batch_size * 3  # Check more than batch_size to find ready items

        while len(items) < batch_size and checked < max_check:
            raw = self.redis.rpop(DLQ_KEY)
            if raw is None:
                break
            checked += 1

            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("DLQ: invalid JSON entry, discarding")
                continue

            if entry.get("next_retry_at", 0) > now:
                # Not ready yet, put it back
                self.redis.lpush(DLQ_KEY, raw)
                continue

            if entry["retry_count"] >= entry.get("max_retries", self.max_retries):
                logger.warning(
                    "DLQ: exhausted retries for subscriber=%s, discarding",
                    entry.get("subscriber_id"),
                )
                continue

            # Move to processing
            self.redis.hset(
                DLQ_PROCESSING_KEY, entry["dlq_id"], json.dumps(entry, default=str)
            )
            items.append(entry)

        return items

    def ack(self, dlq_id: str):
        """Acknowledge successful retry — remove from processing set."""
        self.redis.hdel(DLQ_PROCESSING_KEY, dlq_id)
        logger.info("DLQ ack: %s", dlq_id)

    def nack(self, dlq_id: str):
        """Mark retry as failed — increment retry count and re-enqueue or discard."""
        raw = self.redis.hget(DLQ_PROCESSING_KEY, dlq_id)
        self.redis.hdel(DLQ_PROCESSING_KEY, dlq_id)

        if raw is None:
            return

        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            return

        entry["retry_count"] += 1
        if entry["retry_count"] >= entry.get("max_retries", self.max_retries):
            logger.warning(
                "DLQ: exhausted retries for %s after %d attempts",
                dlq_id,
                entry["retry_count"],
            )
            return  # Discard

        # Exponential backoff
        delay = self.base_delay * (2 ** entry["retry_count"])
        entry["next_retry_at"] = time.time() + delay
        self.redis.lpush(DLQ_KEY, json.dumps(entry, default=str))
        logger.info(
            "DLQ nack: %s retry=%d next_retry_in=%.0fs",
            dlq_id,
            entry["retry_count"],
            delay,
        )

    def size(self) -> int:
        """Return the number of items waiting in the DLQ."""
        return self.redis.llen(DLQ_KEY)

    def processing_count(self) -> int:
        """Return the number of items currently being processed."""
        return self.redis.hlen(DLQ_PROCESSING_KEY)

    def to_dict(self) -> dict:
        """Return DLQ status as a dict."""
        return {
            "pending": self.size(),
            "processing": self.processing_count(),
            "max_retries": self.max_retries,
            "base_delay_seconds": self.base_delay,
        }
