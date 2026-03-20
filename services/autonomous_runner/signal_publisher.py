"""Redis channel publisher for raw trading signals.

Publishes generated signals to `channel:raw-signals` so downstream
consumers (scorer, advisor, report agents) can pick them up.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "channel:raw-signals"


class SignalPublisher:
    """Publishes signals to a Redis Pub/Sub channel.

    Handles serialization and graceful failure when Redis is unavailable.
    """

    def __init__(self, redis_client=None, channel: str = DEFAULT_CHANNEL):
        self.redis = redis_client
        self.channel = channel
        self._published_count = 0
        self._failed_count = 0

    def publish(self, signal_data: dict) -> bool:
        """Publish a signal to the Redis channel.

        Args:
            signal_data: Signal dictionary containing at minimum
                symbol, action, confidence, reasoning.

        Returns:
            True if published successfully, False otherwise.
        """
        if self.redis is None:
            logger.debug("No Redis client, skipping signal publish")
            return False

        payload = {
            **signal_data,
            "published_at": time.time(),
        }

        try:
            message = json.dumps(payload, default=str)
            receivers = self.redis.publish(self.channel, message)
            self._published_count += 1
            logger.debug(
                "Published signal to %s (%d receivers): %s %s",
                self.channel,
                receivers,
                signal_data.get("symbol", "?"),
                signal_data.get("action", "?"),
            )
            return True
        except Exception as e:
            self._failed_count += 1
            logger.error("Failed to publish signal to %s: %s", self.channel, e)
            return False

    def publish_batch(self, signals: list[dict]) -> int:
        """Publish multiple signals. Returns count of successfully published."""
        published = 0
        for signal in signals:
            if self.publish(signal):
                published += 1
        return published

    def get_stats(self) -> dict:
        """Return publisher statistics."""
        return {
            "channel": self.channel,
            "published_count": self._published_count,
            "failed_count": self._failed_count,
            "redis_connected": self.redis is not None,
        }
