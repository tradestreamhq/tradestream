"""Tests for distributed run locks."""

import json
import time

import pytest

from services.autonomous_runner.run_lock import (
    HEARTBEAT_KEY_TEMPLATE,
    LOCK_KEY_TEMPLATE,
    LOCK_STALE_THRESHOLD,
    LOCK_TTL,
    HeartbeatManager,
    LockManager,
    RunLock,
    StaleLockRecovery,
)


class FakeRedis:
    """Minimal Redis mock for lock tests."""

    def __init__(self):
        self.store = {}
        self.expiries = {}
        self._eval_handler = None

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex:
            self.expiries[key] = time.time() + ex
        return True

    def get(self, key):
        if key in self.expiries and time.time() > self.expiries[key]:
            del self.store[key]
            del self.expiries[key]
            return None
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)
        self.expiries.pop(key, None)

    def exists(self, key):
        if key in self.expiries and time.time() > self.expiries[key]:
            del self.store[key]
            del self.expiries[key]
            return False
        return key in self.store

    def eval(self, script, num_keys, *args):
        """Simple Lua script emulation for lock release and recovery."""
        if num_keys == 1:
            key = args[0]
            if "DEL" in script and "NX" not in script:
                # Release script
                instance_id = args[1]
                data = self.get(key)
                if data:
                    parsed = json.loads(data)
                    if parsed.get("instance_id") == instance_id:
                        self.delete(key)
                        return 1
                return 0
            elif "NX" in script:
                # Recovery script
                new_value = args[1]
                owner = args[2]
                ttl = int(args[3])
                current = self.get(key)
                if current:
                    parsed = json.loads(current)
                    if parsed.get("instance_id") == owner:
                        self.delete(key)
                return self.set(key, new_value, nx=True, ex=ttl)
        return None

    def publish(self, channel, message):
        return 0


class TestRunLock:
    def test_acquire_and_release(self):
        redis = FakeRedis()
        lock = RunLock(redis, "inst-1")
        assert lock.acquire("BTC-USD") is True
        assert lock.release("BTC-USD") is True

    def test_acquire_blocked_by_other(self):
        redis = FakeRedis()
        lock1 = RunLock(redis, "inst-1")
        lock2 = RunLock(redis, "inst-2")
        assert lock1.acquire("BTC-USD") is True
        assert lock2.acquire("BTC-USD") is False

    def test_release_only_owner(self):
        redis = FakeRedis()
        lock1 = RunLock(redis, "inst-1")
        lock2 = RunLock(redis, "inst-2")
        lock1.acquire("ETH-USD")
        # inst-2 should not be able to release inst-1's lock
        assert lock2.release("ETH-USD") is False
        # inst-1 can release
        assert lock1.release("ETH-USD") is True

    def test_acquire_after_release(self):
        redis = FakeRedis()
        lock1 = RunLock(redis, "inst-1")
        lock2 = RunLock(redis, "inst-2")
        lock1.acquire("SOL-USD")
        lock1.release("SOL-USD")
        assert lock2.acquire("SOL-USD") is True

    def test_get_lock_info(self):
        redis = FakeRedis()
        lock = RunLock(redis, "inst-1")
        lock.acquire("BTC-USD")
        info = lock.get_lock_info("BTC-USD")
        assert info is not None
        assert info.instance_id == "inst-1"
        assert info.symbol == "BTC-USD"

    def test_get_lock_info_no_lock(self):
        redis = FakeRedis()
        lock = RunLock(redis, "inst-1")
        assert lock.get_lock_info("BTC-USD") is None

    def test_acquire_handles_redis_error(self):
        class BrokenRedis:
            def set(self, *args, **kwargs):
                raise ConnectionError("Redis down")

        lock = RunLock(BrokenRedis(), "inst-1")
        assert lock.acquire("BTC-USD") is False


class TestStaleLockRecovery:
    def test_no_lock_to_recover(self):
        redis = FakeRedis()
        recovery = StaleLockRecovery(redis, "inst-2")
        assert recovery.check_and_recover("BTC-USD") is False

    def test_recover_stale_by_age(self):
        redis = FakeRedis()
        # Place a stale lock (old timestamp)
        key = LOCK_KEY_TEMPLATE.format(symbol="BTC-USD")
        stale_data = json.dumps(
            {
                "instance_id": "dead-inst",
                "acquired_at": time.time() - LOCK_STALE_THRESHOLD - 10,
                "pid": 9999,
            }
        )
        redis.set(key, stale_data)

        recovery = StaleLockRecovery(redis, "inst-2")
        assert recovery.check_and_recover("BTC-USD") is True
        assert recovery.recovered_count == 1

    def test_recover_stale_by_missing_heartbeat(self):
        redis = FakeRedis()
        key = LOCK_KEY_TEMPLATE.format(symbol="ETH-USD")
        lock_data = json.dumps(
            {
                "instance_id": "dead-inst",
                "acquired_at": time.time() - 10,  # Not stale by age
                "pid": 9999,
            }
        )
        redis.set(key, lock_data)
        # No heartbeat for dead-inst

        recovery = StaleLockRecovery(redis, "inst-2")
        assert recovery.check_and_recover("ETH-USD") is True

    def test_no_recovery_when_alive(self):
        redis = FakeRedis()
        key = LOCK_KEY_TEMPLATE.format(symbol="SOL-USD")
        lock_data = json.dumps(
            {
                "instance_id": "live-inst",
                "acquired_at": time.time(),
                "pid": 1234,
            }
        )
        redis.set(key, lock_data)
        # Set heartbeat for live-inst
        hb_key = HEARTBEAT_KEY_TEMPLATE.format(instance_id="live-inst")
        redis.set(hb_key, json.dumps({"timestamp": time.time()}), ex=30)

        recovery = StaleLockRecovery(redis, "inst-2")
        assert recovery.check_and_recover("SOL-USD") is False


class TestLockManager:
    def test_acquire_normal(self):
        redis = FakeRedis()
        mgr = LockManager(redis, "inst-1")
        assert mgr.acquire("BTC-USD") is True

    def test_acquire_with_recovery(self):
        redis = FakeRedis()
        # Place stale lock
        key = LOCK_KEY_TEMPLATE.format(symbol="BTC-USD")
        redis.set(
            key,
            json.dumps(
                {
                    "instance_id": "dead",
                    "acquired_at": time.time() - LOCK_STALE_THRESHOLD - 10,
                }
            ),
        )

        mgr = LockManager(redis, "inst-2")
        assert mgr.acquire("BTC-USD") is True

    def test_acquire_blocked(self):
        redis = FakeRedis()
        mgr1 = LockManager(redis, "inst-1")
        mgr2 = LockManager(redis, "inst-2")
        mgr1.acquire("BTC-USD")
        # Set heartbeat so recovery won't trigger
        hb_key = HEARTBEAT_KEY_TEMPLATE.format(instance_id="inst-1")
        redis.set(hb_key, json.dumps({"timestamp": time.time()}), ex=30)

        assert mgr2.acquire("BTC-USD") is False

    def test_release(self):
        redis = FakeRedis()
        mgr = LockManager(redis, "inst-1")
        mgr.acquire("BTC-USD")
        assert mgr.release("BTC-USD") is True

    def test_get_status(self):
        redis = FakeRedis()
        mgr = LockManager(redis, "inst-1")
        status = mgr.get_status()
        assert status["instance_id"] == "inst-1"
        assert status["stale_locks_recovered"] == 0
