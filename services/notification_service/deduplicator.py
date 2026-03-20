"""Cross-channel signal deduplication."""

import time


class CrossChannelDeduplicator:
    """Prevents duplicate signal delivery across channels for a user.

    Uses Redis to track which (user, signal) pairs have been delivered.
    Supports three delivery modes:
      - primary_only: send to primary channel only
      - all_enabled: send to all enabled channels
      - fallback_chain: try primary, fallback on failure
    """

    TTL_SECONDS = 3600  # 1-hour dedup window

    def __init__(self, redis_client):
        self.redis = redis_client

    def should_deliver(
        self,
        signal_id: str,
        user_id: str,
        channel: str,
        preference: str = "primary_only",
        primary_channel: str = "",
    ) -> bool:
        """Check if a signal should be delivered to this channel.

        Args:
            signal_id: Unique signal identifier.
            user_id: Target user.
            channel: Delivery channel name.
            preference: One of primary_only, all_enabled, fallback_chain.
            primary_channel: The user's primary channel (for primary_only / fallback_chain).

        Returns:
            True if delivery should proceed.
        """
        if preference == "all_enabled":
            # Check per-channel dedup only
            key = f"dedup:{user_id}:{signal_id}:{channel}"
            return self._try_claim(key)

        if preference == "fallback_chain":
            return self._check_fallback(signal_id, user_id, channel)

        # primary_only (default)
        if primary_channel and channel != primary_channel:
            return False
        key = f"dedup:{user_id}:{signal_id}"
        return self._try_claim(key)

    def mark_failed(self, signal_id: str, user_id: str, channel: str):
        """Mark a channel delivery as failed (enables fallback)."""
        key = f"dedup:{user_id}:{signal_id}:failed:{channel}"
        self.redis.setex(key, self.TTL_SECONDS, "1")

    def _check_fallback(self, signal_id: str, user_id: str, channel: str) -> bool:
        """Fallback chain: deliver if no other channel has succeeded."""
        success_key = f"dedup:{user_id}:{signal_id}:success"
        if self.redis.exists(success_key):
            return False
        per_channel_key = f"dedup:{user_id}:{signal_id}:{channel}"
        return self._try_claim(per_channel_key)

    def mark_success(self, signal_id: str, user_id: str):
        """Mark that this signal was successfully delivered to the user."""
        key = f"dedup:{user_id}:{signal_id}:success"
        self.redis.setex(key, self.TTL_SECONDS, "1")

    def _try_claim(self, key: str) -> bool:
        """Atomically claim a dedup slot. Returns True if this is the first claim."""
        result = self.redis.set(key, "1", nx=True, ex=self.TTL_SECONDS)
        return bool(result)
