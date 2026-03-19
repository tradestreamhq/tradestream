"""Cross-channel deduplication for signal delivery."""


class CrossChannelDeduplicator:
    """Prevents the same signal from being sent multiple times to a user.

    Uses Redis to track which signals have been delivered to which users,
    supporting three deduplication strategies:
      - primary_only: only deliver to primary channel (default)
      - all_enabled: deliver to all enabled channels
      - fallback_chain: try primary, then fallback channels if primary fails
    """

    def __init__(self, redis_client, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    def should_deliver(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        preference: str = "primary_only",
    ) -> bool:
        """Check if a signal should be delivered to this channel."""
        if preference == "all_enabled":
            return True

        key = f"dedup:{user_id}:{signal_id}"
        delivered_channels = self.redis.smembers(key)

        if preference == "primary_only":
            return len(delivered_channels) == 0

        if preference == "fallback_chain":
            # Allow delivery if no previous channel succeeded
            return all(
                self._channel_failed(signal_id, user_id, ch)
                for ch in delivered_channels
            )

        return True

    def mark_delivered(self, signal_id: str, user_id: str, channel: str) -> None:
        """Record successful delivery to a channel."""
        key = f"dedup:{user_id}:{signal_id}"
        self.redis.sadd(key, channel)
        self.redis.expire(key, self.ttl_seconds)

    def mark_failed(self, signal_id: str, user_id: str, channel: str) -> None:
        """Record failed delivery to a channel."""
        fail_key = f"dedup:fail:{user_id}:{signal_id}:{channel}"
        self.redis.setex(fail_key, self.ttl_seconds, "1")

    def _channel_failed(self, signal_id: str, user_id: str, channel: str) -> bool:
        """Check if delivery to a specific channel failed."""
        fail_key = f"dedup:fail:{user_id}:{signal_id}:{channel}"
        return bool(self.redis.exists(fail_key))
