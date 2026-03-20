"""Tests for kill switch."""

import json

from services.autonomous_runner.config import KillSwitchConfig
from services.autonomous_runner.kill_switch import KillSwitch


class FakeRedis:
    """Minimal Redis mock for testing."""

    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)


class TestKillSwitch:
    def _make_switch(self) -> tuple:
        redis = FakeRedis()
        config = KillSwitchConfig(redis_key="test:kill_switch", check_interval_seconds=0)
        ks = KillSwitch(redis, config)
        return ks, redis

    def test_default_inactive(self):
        ks, _ = self._make_switch()
        assert ks.is_active() is False

    def test_activate(self):
        ks, _ = self._make_switch()
        success = ks.activate(reason="test", activated_by="unit_test")
        assert success is True
        assert ks.is_active() is True

    def test_deactivate(self):
        ks, _ = self._make_switch()
        ks.activate(reason="test")
        ks.deactivate(deactivated_by="unit_test")
        assert ks.is_active() is False

    def test_get_status_when_active(self):
        ks, _ = self._make_switch()
        ks.activate(reason="maintenance", activated_by="admin")
        status = ks.get_status()
        assert status["active"] is True
        assert status["reason"] == "maintenance"
        assert status["activated_by"] == "admin"

    def test_get_status_when_inactive(self):
        ks, _ = self._make_switch()
        status = ks.get_status()
        assert status["active"] is False

    def test_caching_respects_interval(self):
        ks, redis = self._make_switch()
        # First check - returns False
        assert ks.is_active() is False

        # Manually set in Redis
        redis.set(
            "test:kill_switch",
            json.dumps({"active": True, "reason": "manual"}),
        )

        # Since check_interval_seconds=0, it should re-check immediately
        assert ks.is_active() is True

    def test_redis_failure_uses_cache(self):
        ks, _ = self._make_switch()

        class FailingRedis:
            def get(self, key):
                raise ConnectionError("Redis down")

            def set(self, key, value):
                raise ConnectionError("Redis down")

            def delete(self, key):
                raise ConnectionError("Redis down")

        ks.redis = FailingRedis()
        # Should return cached value (False) without raising
        assert ks.is_active() is False
