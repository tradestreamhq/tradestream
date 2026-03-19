"""In-process TTL cache for MCP servers.

Provides a simple time-based cache with force_refresh support per the MCP servers spec.
"""

import time
from typing import Any, Optional


class TtlCache:
    """Simple in-memory TTL cache.

    Thread-safe for single-threaded async usage (one event loop).
    """

    def __init__(self, default_ttl: float = 30.0):
        """Initialize cache with a default TTL in seconds."""
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[tuple[Any, float]]:
        """Get a cached value if not expired.

        Returns:
            Tuple of (value, ttl_remaining) or None if expired/missing.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        remaining = expires_at - time.monotonic()
        if remaining <= 0:
            del self._store[key]
            return None
        return value, remaining

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store a value with TTL."""
        t = ttl if ttl is not None else self.default_ttl
        self._store[key] = (value, time.monotonic() + t)

    def invalidate(self, key: str) -> None:
        """Remove a specific key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
