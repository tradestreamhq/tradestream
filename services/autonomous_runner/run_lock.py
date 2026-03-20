"""Distributed run locks for the autonomous signal pipeline.

Prevents multiple instances from processing the same symbol concurrently.
Uses Redis SET NX with TTL for lock acquisition and Lua scripts for
atomic release (only the owner can release).

Includes stale lock recovery via heartbeats.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

LOCK_KEY_TEMPLATE = "signal:lock:{symbol}"
HEARTBEAT_KEY_TEMPLATE = "runner:heartbeat:{instance_id}"
LOCK_TTL = 90  # seconds
LOCK_STALE_THRESHOLD = 120  # seconds
HEARTBEAT_TTL = 30  # seconds
HEARTBEAT_INTERVAL = 10  # seconds

# Lua script for atomic release (only owner can release)
RELEASE_LOCK_SCRIPT = """
local lock_data = redis.call('GET', KEYS[1])
if lock_data then
    local data = cjson.decode(lock_data)
    if data.instance_id == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
end
return 0
"""

# Lua script for atomic stale lock recovery
RECOVER_LOCK_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if current then
    local data = cjson.decode(current)
    if data.instance_id == ARGV[2] then
        redis.call('DEL', KEYS[1])
    end
end
return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3])
"""


@dataclass
class LockInfo:
    """Information about a held lock."""

    symbol: str
    instance_id: str
    acquired_at: float
    pid: int


class RunLock:
    """Distributed lock for per-symbol processing.

    Uses Redis SET NX with TTL for lock acquisition and Lua scripts
    for atomic release. Only the owner instance can release a lock.
    """

    def __init__(self, redis_client, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id

    def acquire(self, symbol: str) -> bool:
        """Try to acquire the processing lock for a symbol.

        Returns True if the lock was acquired.
        """
        key = LOCK_KEY_TEMPLATE.format(symbol=symbol)
        lock_value = json.dumps(
            {
                "instance_id": self.instance_id,
                "acquired_at": time.time(),
                "pid": os.getpid(),
            }
        )
        try:
            result = self.redis.set(key, lock_value, nx=True, ex=LOCK_TTL)
            if result:
                logger.debug("Acquired lock for %s", symbol)
            return bool(result)
        except Exception as e:
            logger.error("Failed to acquire lock for %s: %s", symbol, e)
            return False

    def release(self, symbol: str) -> bool:
        """Release the lock if this instance owns it.

        Uses a Lua script for atomicity.
        """
        key = LOCK_KEY_TEMPLATE.format(symbol=symbol)
        try:
            result = self.redis.eval(RELEASE_LOCK_SCRIPT, 1, key, self.instance_id)
            released = result == 1
            if released:
                logger.debug("Released lock for %s", symbol)
            return released
        except Exception as e:
            logger.error("Failed to release lock for %s: %s", symbol, e)
            return False

    def get_lock_info(self, symbol: str) -> Optional[LockInfo]:
        """Get information about the current lock holder."""
        key = LOCK_KEY_TEMPLATE.format(symbol=symbol)
        try:
            data = self.redis.get(key)
            if data is None:
                return None
            info = json.loads(data)
            return LockInfo(
                symbol=symbol,
                instance_id=info["instance_id"],
                acquired_at=info["acquired_at"],
                pid=info.get("pid", 0),
            )
        except Exception:
            return None


class HeartbeatManager:
    """Maintains a heartbeat to indicate this runner instance is alive.

    Other instances check heartbeats to detect crashed processes
    and recover stale locks.
    """

    def __init__(self, redis_client, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the heartbeat background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        self._thread.start()
        logger.info("Heartbeat started for instance %s", self.instance_id)

    def stop(self):
        """Stop the heartbeat."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        # Clean up heartbeat key
        key = HEARTBEAT_KEY_TEMPLATE.format(instance_id=self.instance_id)
        try:
            self.redis.delete(key)
        except Exception:
            pass
        logger.info("Heartbeat stopped for instance %s", self.instance_id)

    def _heartbeat_loop(self):
        """Maintain heartbeat at regular intervals."""
        key = HEARTBEAT_KEY_TEMPLATE.format(instance_id=self.instance_id)
        while not self._stop_event.is_set():
            try:
                payload = json.dumps({"timestamp": time.time(), "pid": os.getpid()})
                self.redis.set(key, payload, ex=HEARTBEAT_TTL)
            except Exception as e:
                logger.error("Heartbeat failed: %s", e)
            self._stop_event.wait(timeout=HEARTBEAT_INTERVAL)


class StaleLockRecovery:
    """Detects and recovers stale locks from crashed instances.

    A lock is considered stale if:
    1. It has existed longer than LOCK_STALE_THRESHOLD, OR
    2. The owning instance's heartbeat is missing
    """

    def __init__(self, redis_client, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id
        self._recovered_count = 0

    def check_and_recover(self, symbol: str) -> bool:
        """Check if a lock is stale and recover it.

        Returns True if the lock was recovered and acquired by this instance.
        """
        key = LOCK_KEY_TEMPLATE.format(symbol=symbol)
        try:
            raw = self.redis.get(key)
        except Exception:
            return False

        if raw is None:
            return False

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False

        lock_age = time.time() - data.get("acquired_at", 0)
        owner = data.get("instance_id", "")

        should_recover = False
        reason = ""

        # Check age
        if lock_age > LOCK_STALE_THRESHOLD:
            should_recover = True
            reason = f"age={lock_age:.0f}s exceeds threshold={LOCK_STALE_THRESHOLD}s"

        # Check heartbeat
        if not should_recover and owner:
            hb_key = HEARTBEAT_KEY_TEMPLATE.format(instance_id=owner)
            try:
                if not self.redis.exists(hb_key):
                    should_recover = True
                    reason = f"owner {owner} heartbeat missing"
            except Exception:
                pass

        if not should_recover:
            return False

        logger.warning("Recovering stale lock for %s: %s", symbol, reason)

        # Atomic delete-and-acquire
        new_value = json.dumps(
            {
                "instance_id": self.instance_id,
                "acquired_at": time.time(),
                "pid": os.getpid(),
            }
        )
        try:
            result = self.redis.eval(
                RECOVER_LOCK_SCRIPT,
                1,
                key,
                new_value,
                owner,
                str(LOCK_TTL),
            )
            if result is not None:
                self._recovered_count += 1
                return True
        except Exception as e:
            logger.error("Stale lock recovery failed for %s: %s", symbol, e)

        return False

    @property
    def recovered_count(self) -> int:
        return self._recovered_count


class LockManager:
    """High-level lock manager combining RunLock and StaleLockRecovery."""

    def __init__(self, redis_client, instance_id: str):
        self.lock = RunLock(redis_client, instance_id)
        self.recovery = StaleLockRecovery(redis_client, instance_id)
        self.heartbeat = HeartbeatManager(redis_client, instance_id)
        self.instance_id = instance_id

    def acquire(self, symbol: str) -> bool:
        """Try to acquire lock, recovering stale locks if needed."""
        if self.lock.acquire(symbol):
            return True
        # Normal acquisition failed — check for stale lock
        if self.recovery.check_and_recover(symbol):
            return True
        return False

    def release(self, symbol: str) -> bool:
        """Release lock if we own it."""
        return self.lock.release(symbol)

    def start_heartbeat(self):
        """Start the heartbeat manager."""
        self.heartbeat.start()

    def stop_heartbeat(self):
        """Stop the heartbeat manager."""
        self.heartbeat.stop()

    def get_status(self) -> dict:
        """Return lock manager status."""
        return {
            "instance_id": self.instance_id,
            "stale_locks_recovered": self.recovery.recovered_count,
        }
