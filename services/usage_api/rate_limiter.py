"""Sliding window rate limiter with per-tier quota enforcement.

Uses an in-memory sliding window counter to track API calls per user
per endpoint. Supports configurable rate limits per subscription tier.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TierConfig:
    """Rate limit configuration for a subscription tier."""

    name: str
    requests_per_hour: int


# Default tier configurations
TIER_CONFIGS: Dict[str, TierConfig] = {
    "free": TierConfig(name="free", requests_per_hour=100),
    "basic": TierConfig(name="basic", requests_per_hour=1_000),
    "pro": TierConfig(name="pro", requests_per_hour=10_000),
}

WINDOW_SIZE_SECONDS = 3600  # 1 hour


@dataclass
class UsageRecord:
    """A single API usage record."""

    endpoint: str
    timestamp: float


@dataclass
class _UserBucket:
    """Thread-safe sliding window counter for a single user."""

    records: List[UsageRecord] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter.

    Tracks API calls per user and enforces per-tier hourly quotas.
    The sliding window evicts expired entries on each check.
    """

    def __init__(
        self,
        tier_configs: Optional[Dict[str, TierConfig]] = None,
        window_seconds: int = WINDOW_SIZE_SECONDS,
    ):
        self._tier_configs = tier_configs or TIER_CONFIGS
        self._window_seconds = window_seconds
        self._buckets: Dict[str, _UserBucket] = defaultdict(_UserBucket)
        self._user_tiers: Dict[str, str] = {}
        self._global_lock = threading.Lock()

    def set_user_tier(self, user_id: str, tier: str) -> None:
        """Assign a subscription tier to a user."""
        if tier not in self._tier_configs:
            raise ValueError(f"Unknown tier: {tier}. Valid: {list(self._tier_configs)}")
        self._user_tiers[user_id] = tier

    def get_user_tier(self, user_id: str) -> str:
        """Return the tier for a user, defaulting to 'free'."""
        return self._user_tiers.get(user_id, "free")

    def _get_bucket(self, user_id: str) -> _UserBucket:
        with self._global_lock:
            return self._buckets[user_id]

    def _evict_expired(self, bucket: _UserBucket, now: float) -> None:
        """Remove records outside the sliding window. Must hold bucket lock."""
        cutoff = now - self._window_seconds
        bucket.records = [r for r in bucket.records if r.timestamp > cutoff]

    def check_and_record(
        self, user_id: str, endpoint: str
    ) -> Tuple[bool, int, int, float]:
        """Check rate limit and record the request if allowed.

        Returns:
            (allowed, limit, remaining, reset_timestamp)
        """
        now = time.time()
        tier = self.get_user_tier(user_id)
        config = self._tier_configs[tier]
        limit = config.requests_per_hour

        bucket = self._get_bucket(user_id)
        with bucket.lock:
            self._evict_expired(bucket, now)
            current_count = len(bucket.records)
            remaining = max(0, limit - current_count)
            reset_ts = now + self._window_seconds

            if current_count >= limit:
                # Find the earliest record to compute when a slot frees up
                if bucket.records:
                    reset_ts = bucket.records[0].timestamp + self._window_seconds
                return False, limit, 0, reset_ts

            bucket.records.append(UsageRecord(endpoint=endpoint, timestamp=now))
            remaining = max(0, limit - current_count - 1)
            return True, limit, remaining, reset_ts

    def get_current_usage(self, user_id: str) -> Dict:
        """Get current usage statistics for a user."""
        now = time.time()
        tier = self.get_user_tier(user_id)
        config = self._tier_configs[tier]

        bucket = self._get_bucket(user_id)
        with bucket.lock:
            self._evict_expired(bucket, now)

            # Count per endpoint
            endpoint_counts: Dict[str, int] = defaultdict(int)
            for record in bucket.records:
                endpoint_counts[record.endpoint] += 1

            total = len(bucket.records)
            return {
                "user_id": user_id,
                "tier": tier,
                "window_seconds": self._window_seconds,
                "limit": config.requests_per_hour,
                "used": total,
                "remaining": max(0, config.requests_per_hour - total),
                "endpoints": dict(endpoint_counts),
            }

    def get_usage_history(self, user_id: str, days: int = 30) -> List[Dict]:
        """Get daily usage breakdown for a user.

        Note: In-memory storage only retains the current window.
        A production implementation would query a persistent store.
        This returns available data bucketed by day.
        """
        now = time.time()
        bucket = self._get_bucket(user_id)
        with bucket.lock:
            # We only have records within the current window
            daily: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for record in bucket.records:
                day = time.strftime("%Y-%m-%d", time.gmtime(record.timestamp))
                daily[day][record.endpoint] += 1

            result = []
            for day_str, endpoints in sorted(daily.items()):
                total = sum(endpoints.values())
                result.append(
                    {
                        "date": day_str,
                        "total_requests": total,
                        "endpoints": dict(endpoints),
                    }
                )
            return result
