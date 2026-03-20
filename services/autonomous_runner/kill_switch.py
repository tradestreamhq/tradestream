"""Kill switch for autonomous signal generation.

Provides manual override to pause all autonomous signal generation.
Can be triggered via Redis key, API endpoint, or environment variable.
"""

import json
import logging
import time

logger = logging.getLogger(__name__)


class KillSwitch:
    """Manual override to pause autonomous signal generation.

    The kill switch state is stored in Redis so it persists across restarts
    and can be toggled from any service or admin tool.
    """

    def __init__(self, redis_client, config):
        self.redis = redis_client
        self.config = config
        self._local_cache = False
        self._last_check = 0.0

    def is_active(self) -> bool:
        """Check if the kill switch is engaged.

        Caches the result for check_interval_seconds to avoid
        hammering Redis on every cycle.
        """
        now = time.time()
        if now - self._last_check < self.config.check_interval_seconds:
            return self._local_cache

        self._last_check = now
        try:
            value = self.redis.get(self.config.redis_key)
            if value is None:
                self._local_cache = False
                return False
            data = json.loads(value)
            self._local_cache = data.get("active", False)
            return self._local_cache
        except Exception as e:
            logger.error("Failed to check kill switch: %s", e)
            # If we can't check, assume not active (fail open)
            return self._local_cache

    def activate(self, reason: str = "", activated_by: str = "system") -> bool:
        """Activate the kill switch, pausing all autonomous generation."""
        try:
            data = {
                "active": True,
                "reason": reason,
                "activated_by": activated_by,
                "activated_at": time.time(),
            }
            self.redis.set(self.config.redis_key, json.dumps(data))
            self._local_cache = True
            logger.warning(
                "Kill switch ACTIVATED by %s: %s", activated_by, reason
            )
            return True
        except Exception as e:
            logger.error("Failed to activate kill switch: %s", e)
            return False

    def deactivate(self, deactivated_by: str = "system") -> bool:
        """Deactivate the kill switch, resuming autonomous generation."""
        try:
            self.redis.delete(self.config.redis_key)
            self._local_cache = False
            logger.info("Kill switch DEACTIVATED by %s", deactivated_by)
            return True
        except Exception as e:
            logger.error("Failed to deactivate kill switch: %s", e)
            return False

    def get_status(self) -> dict:
        """Return current kill switch status."""
        try:
            value = self.redis.get(self.config.redis_key)
            if value is None:
                return {"active": False}
            return json.loads(value)
        except Exception as e:
            logger.error("Failed to get kill switch status: %s", e)
            return {"active": self._local_cache, "error": str(e)}
