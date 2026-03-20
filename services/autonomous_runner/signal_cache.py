"""Signal caching layer with Redis backend and local fallback.

Caches MCP tool results (strategies, market data, signals) with configurable
TTLs per data type. Falls back to in-memory cache when Redis is unavailable.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """TTL configuration for different data types."""

    strategy_list_ttl: float = 300.0  # 5 min
    strategy_signal_ttl: float = 60.0  # 1 min
    market_price_ttl: float = 10.0  # 10 sec
    volatility_ttl: float = 60.0  # 1 min
    degraded_strategy_ttl: float = 600.0  # 10 min fallback
    degraded_price_ttl: float = 120.0  # 2 min fallback
    redis_key_prefix: str = "signal-gen:cache:"
    local_fallback_enabled: bool = True


# Map data type to (normal TTL field, degraded TTL field)
_TTL_MAP = {
    "strategies": ("strategy_list_ttl", "degraded_strategy_ttl"),
    "strategy_signal": ("strategy_signal_ttl", "strategy_signal_ttl"),
    "market_price": ("market_price_ttl", "degraded_price_ttl"),
    "volatility": ("volatility_ttl", "volatility_ttl"),
    "market_summary": ("market_price_ttl", "degraded_price_ttl"),
    "recent_signals": ("strategy_signal_ttl", "strategy_signal_ttl"),
}


@dataclass
class CacheStats:
    """Cache hit/miss statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class SignalCache:
    """Two-tier cache: Redis primary with in-memory fallback.

    Usage:
        cache = SignalCache(redis_client=r, config=CacheConfig())
        # Try cache first
        data = cache.get("strategies", "BTC-USD")
        if data is None:
            data = fetch_from_mcp(...)
            cache.put("strategies", "BTC-USD", data)
    """

    def __init__(self, redis_client=None, config: Optional[CacheConfig] = None):
        self.redis = redis_client
        self.config = config or CacheConfig()
        self._local: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self.stats = CacheStats()

    def get(
        self, data_type: str, key: str, degraded: bool = False
    ) -> Optional[Any]:
        """Get a cached value.

        Args:
            data_type: One of strategies, strategy_signal, market_price, etc.
            key: Cache key (typically symbol or strategy_id:symbol).
            degraded: If True, use longer degraded-mode TTLs.

        Returns:
            Cached value or None if miss/expired.
        """
        full_key = self._full_key(data_type, key)
        ttl = self._get_ttl(data_type, degraded)

        # Try Redis first
        if self.redis is not None:
            try:
                raw = self.redis.get(full_key)
                if raw is not None:
                    payload = json.loads(raw)
                    cached_at = payload.get("cached_at", 0)
                    if time.time() - cached_at < ttl:
                        self.stats.hits += 1
                        return payload["value"]
            except Exception:
                self.stats.errors += 1

        # Fall back to local cache
        if self.config.local_fallback_enabled:
            entry = self._local.get(full_key)
            if entry is not None:
                value, expires_at = entry
                if time.time() < expires_at:
                    self.stats.hits += 1
                    return value
                else:
                    del self._local[full_key]

        self.stats.misses += 1
        return None

    def put(self, data_type: str, key: str, value: Any) -> None:
        """Store a value in cache with appropriate TTL.

        Args:
            data_type: Data type for TTL lookup.
            key: Cache key.
            value: Data to cache.
        """
        full_key = self._full_key(data_type, key)
        ttl = self._get_ttl(data_type, degraded=False)
        payload = {"value": value, "cached_at": time.time()}

        # Write to Redis
        if self.redis is not None:
            try:
                self.redis.setex(full_key, int(ttl), json.dumps(payload, default=str))
                self.stats.sets += 1
            except Exception:
                self.stats.errors += 1

        # Always write to local fallback
        if self.config.local_fallback_enabled:
            self._local[full_key] = (value, time.time() + ttl)
            self.stats.sets += 1

    def invalidate(self, data_type: str, key: str) -> None:
        """Remove a specific entry from both caches."""
        full_key = self._full_key(data_type, key)
        if self.redis is not None:
            try:
                self.redis.delete(full_key)
            except Exception:
                pass
        self._local.pop(full_key, None)

    def clear(self) -> None:
        """Clear all local cache entries."""
        self._local.clear()

    def get_stats(self) -> dict:
        """Return cache statistics."""
        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "sets": self.stats.sets,
            "errors": self.stats.errors,
            "hit_rate": round(self.stats.hit_rate, 3),
            "local_entries": len(self._local),
        }

    def _full_key(self, data_type: str, key: str) -> str:
        return f"{self.config.redis_key_prefix}{data_type}:{key}"

    def _get_ttl(self, data_type: str, degraded: bool) -> float:
        ttl_fields = _TTL_MAP.get(data_type)
        if ttl_fields is None:
            return 60.0  # default 1 min
        field_name = ttl_fields[1] if degraded else ttl_fields[0]
        return getattr(self.config, field_name, 60.0)
