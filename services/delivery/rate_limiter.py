"""Rate limiting for signal delivery with user tier support."""


class DeliveryRateLimiter:
    """Per-user, per-channel rate limiting with tier multipliers.

    Messaging channels (telegram, discord, slack): 1 signal per symbol per window.
    SMS: limited total count per hour.
    Email: limited total count per hour.
    """

    TIER_MULTIPLIERS = {
        "free": 1.0,
        "pro": 2.0,
        "power": 3.0,
    }

    DEFAULT_LIMITS = {
        "telegram": {"per_symbol_seconds": 300},
        "discord": {"per_symbol_seconds": 300},
        "slack": {"per_symbol_seconds": 300},
        "webhook": {"per_symbol_seconds": 60},
        "sms": {"per_hour": 5},
        "email": {"per_hour": 20},
    }

    def __init__(self, redis_client):
        self.redis = redis_client

    def is_rate_limited(
        self,
        user_id: str,
        channel: str,
        symbol: str,
        user_tier: str = "free",
    ) -> bool:
        """Check if delivery to this user/channel/symbol is rate-limited."""
        channel_limits = self.DEFAULT_LIMITS.get(channel, {})
        multiplier = self.TIER_MULTIPLIERS.get(user_tier, 1.0)

        if "per_symbol_seconds" in channel_limits:
            return self._check_per_symbol(
                user_id,
                channel,
                symbol,
                channel_limits["per_symbol_seconds"],
                multiplier,
            )
        elif "per_hour" in channel_limits:
            return self._check_per_hour(
                user_id, channel, channel_limits["per_hour"], multiplier
            )
        return False

    def _check_per_symbol(
        self,
        user_id: str,
        channel: str,
        symbol: str,
        window_seconds: int,
        multiplier: float,
    ) -> bool:
        """Check per-symbol rate limit."""
        adjusted_window = max(1, int(window_seconds / multiplier))
        key = f"ratelimit:{channel}:{user_id}:{symbol}"
        if self.redis.exists(key):
            return True
        self.redis.setex(key, adjusted_window, "1")
        return False

    def _check_per_hour(
        self,
        user_id: str,
        channel: str,
        max_per_hour: int,
        multiplier: float,
    ) -> bool:
        """Check hourly count rate limit."""
        adjusted_max = int(max_per_hour * multiplier)
        key = f"ratelimit:{channel}:{user_id}:hourly"
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, 3600)
        return current > adjusted_max
