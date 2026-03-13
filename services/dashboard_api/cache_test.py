"""Tests for the TTL cache."""

import time
from unittest.mock import patch

from services.dashboard_api.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key1", {"data": "value"})
        assert cache.get("key1") == {"data": "value"}

    def test_get_missing_key(self):
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry(self):
        cache = TTLCache(default_ttl=1)
        cache.set("key1", "value")
        # Simulate expiry by manipulating internal state
        cache._store["key1"] = ("value", time.monotonic() - 1)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = TTLCache(default_ttl=60)
        cache.set("short", "value", ttl=1)
        assert cache.get("short") == "value"
        cache._store["short"] = ("value", time.monotonic() - 1)
        assert cache.get("short") is None

    def test_invalidate(self):
        cache = TTLCache()
        cache.set("key1", "value")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_missing_key(self):
        cache = TTLCache()
        cache.invalidate("nonexistent")  # Should not raise

    def test_clear(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_overwrite(self):
        cache = TTLCache()
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"
