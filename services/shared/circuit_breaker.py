"""Circuit breaker for external API calls (Telegram, webhooks, etc).

Prevents cascading failures by temporarily halting calls to a failing service.
States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery).
"""

import logging
import time
import threading

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker with configurable failure threshold and recovery.

    Usage:
        cb = CircuitBreaker("telegram-api", failure_threshold=5, recovery_timeout=60)

        if cb.allow_request():
            try:
                result = call_telegram_api(...)
                cb.record_success()
            except Exception:
                cb.record_failure()
        else:
            # Circuit is open, skip or queue for retry
            handle_circuit_open()
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._evaluate_state()

    def _evaluate_state(self) -> str:
        """Evaluate the current state, potentially transitioning from OPEN to HALF_OPEN."""
        if self._state == self.STATE_OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.STATE_HALF_OPEN
                self._half_open_calls = 0
                logger.info(
                    "Circuit breaker '%s': OPEN -> HALF_OPEN (recovery timeout elapsed)",
                    self.name,
                )
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through the circuit breaker."""
        with self._lock:
            state = self._evaluate_state()
            if state == self.STATE_CLOSED:
                return True
            if state == self.STATE_HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            return False  # OPEN

    def record_success(self):
        """Record a successful call. Closes the circuit if in HALF_OPEN."""
        with self._lock:
            if self._state == self.STATE_HALF_OPEN:
                self._state = self.STATE_CLOSED
                self._failure_count = 0
                logger.info(
                    "Circuit breaker '%s': HALF_OPEN -> CLOSED (success)",
                    self.name,
                )
            self._success_count += 1
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call. Opens the circuit if threshold is reached."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == self.STATE_HALF_OPEN:
                self._state = self.STATE_OPEN
                logger.warning(
                    "Circuit breaker '%s': HALF_OPEN -> OPEN (failure during probe)",
                    self.name,
                )
            elif (
                self._state == self.STATE_CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = self.STATE_OPEN
                logger.warning(
                    "Circuit breaker '%s': CLOSED -> OPEN after %d failures",
                    self.name,
                    self._failure_count,
                )

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = self.STATE_CLOSED
            self._failure_count = 0
            self._half_open_calls = 0

    def to_dict(self) -> dict:
        """Return circuit breaker state as a dict."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._evaluate_state(),
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }
