"""
In-memory TTL cache for dashboard data.

Provides a simple async-compatible cache with configurable TTL per key.
"""

import time
from typing import Any, Optional


class TTLCache:
    """Simple in-memory cache with per-key TTL support."""

    def __init__(self, default_ttl: int = 30):
        """Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds.
        """
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get a value if it exists and hasn't expired."""
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value with optional TTL override."""
        ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (value, time.monotonic() + ttl)

    def invalidate(self, key: str) -> None:
        """Remove a key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
