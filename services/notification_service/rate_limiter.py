"""Rate limiter for signal delivery channels."""

import time


class DeliveryRateLimiter:
    """Token-bucket rate limiter backed by Redis.

    Enforces per-user, per-channel delivery limits with tier multipliers.
    """

    # Default limits: (max_tokens, window_seconds)
    DEFAULT_LIMITS = {
        "telegram": (20, 3600),  # 20 signals / hour
        "discord": (20, 3600),
        "slack": (20, 3600),
        "webhook": (60, 3600),
        "email": (5, 3600),  # 5 emails / hour
        "sms": (3, 3600),  # 3 SMS / hour (critical only)
    }

    TIER_MULTIPLIERS = {
        "free": 1.0,
        "pro": 2.0,
        "power": 3.0,
    }

    def __init__(self, redis_client, limits: dict | None = None):
        self.redis = redis_client
        self.limits = limits or self.DEFAULT_LIMITS

    def allow(self, user_id: str, channel: str, tier: str = "free") -> bool:
        """Check if a delivery is allowed under the rate limit.

        If allowed, consumes one token. Returns True if allowed.
        """
        max_tokens, window = self.limits.get(channel, (20, 3600))
        multiplier = self.TIER_MULTIPLIERS.get(tier, 1.0)
        effective_limit = int(max_tokens * multiplier)

        key = f"ratelimit:{user_id}:{channel}"
        now = time.time()
        window_start = now - window

        pipe = self.redis.pipeline()
        # Remove expired entries
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Count current entries
        pipe.zcard(key)
        results = pipe.execute()
        current_count = results[1]

        if current_count >= effective_limit:
            return False

        # Add new entry and set expiry
        pipe = self.redis.pipeline()
        pipe.zadd(key, {f"{now}": now})
        pipe.expire(key, window)
        pipe.execute()
        return True

    def remaining(self, user_id: str, channel: str, tier: str = "free") -> int:
        """Return the number of remaining deliveries in the current window."""
        max_tokens, window = self.limits.get(channel, (20, 3600))
        multiplier = self.TIER_MULTIPLIERS.get(tier, 1.0)
        effective_limit = int(max_tokens * multiplier)

        key = f"ratelimit:{user_id}:{channel}"
        window_start = time.time() - window
        self.redis.zremrangebyscore(key, "-inf", window_start)
        current = self.redis.zcard(key)
        return max(0, effective_limit - current)
