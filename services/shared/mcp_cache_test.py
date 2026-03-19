"""Tests for MCP TTL cache."""

import time
from unittest.mock import patch

import pytest

from services.shared.mcp_cache import TtlCache


class TestTtlCache:
    def test_set_and_get(self):
        cache = TtlCache(default_ttl=60)
        cache.set("key1", {"value": 42})
        result = cache.get("key1")
        assert result is not None
        value, ttl_remaining = result
        assert value == {"value": 42}
        assert ttl_remaining > 0

    def test_get_missing(self):
        cache = TtlCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry(self):
        cache = TtlCache(default_ttl=0.01)
        cache.set("key1", "value")
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = TtlCache(default_ttl=60)
        cache.set("key1", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_invalidate(self):
        cache = TtlCache()
        cache.set("key1", "value")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_missing_key(self):
        cache = TtlCache()
        cache.invalidate("nonexistent")  # should not raise

    def test_clear(self):
        cache = TtlCache()
        cache.set("key1", "v1")
        cache.set("key2", "v2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
