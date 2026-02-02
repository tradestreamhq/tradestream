"""Caching utilities for MCP servers."""

import time
import hashlib
import json
from typing import Any, Callable, Dict, Optional, TypeVar
from dataclasses import dataclass
from functools import wraps

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A single cache entry with TTL tracking."""

    value: Any
    expires_at: float
    created_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> Optional[int]:
        remaining = self.expires_at - time.time()
        return max(0, int(remaining)) if remaining > 0 else None


class Cache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 30):
        """Initialize cache with default TTL in seconds."""
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def _make_key(self, prefix: str, **kwargs) -> str:
        """Create a cache key from prefix and kwargs."""
        sorted_items = sorted(kwargs.items())
        key_str = f"{prefix}:{json.dumps(sorted_items, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cache entry if it exists and is not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._cache[key]
            return None
        return entry

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a cache entry with optional custom TTL."""
        ttl = ttl if ttl is not None else self._default_ttl
        now = time.time()
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=now + ttl,
            created_at=now,
        )

    def delete(self, key: str) -> bool:
        """Delete a cache entry. Returns True if entry existed."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


def cached(cache: Cache, prefix: str, ttl: Optional[int] = None):
    """Decorator for caching function results.

    Args:
        cache: The Cache instance to use
        prefix: Prefix for cache keys
        ttl: Optional TTL override for this function

    The decorated function should accept `force_refresh` as a keyword argument.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            force_refresh = kwargs.pop("force_refresh", False)

            # Create cache key from args
            cache_key = cache._make_key(prefix, args=args, kwargs=kwargs)

            # Check cache unless force_refresh
            if not force_refresh:
                entry = cache.get(cache_key)
                if entry is not None:
                    return entry.value

            # Call the function
            result = func(*args, **kwargs)

            # Cache the result
            cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
