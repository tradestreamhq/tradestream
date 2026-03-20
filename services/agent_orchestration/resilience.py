"""Resilience utilities — retry with exponential backoff and circuit breaker."""

import time

from absl import logging

from services.agent_orchestration import config


class CircuitBreaker:
    """Simple circuit breaker to avoid hammering failing services.

    States:
    - CLOSED: requests flow normally, failures are counted
    - OPEN: requests are rejected immediately
    - HALF_OPEN: one probe request allowed to test recovery
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name,
        failure_threshold=None,
        recovery_seconds=None,
    ):
        self.name = name
        self.failure_threshold = (
            failure_threshold or config.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.recovery_seconds = (
            recovery_seconds or config.CIRCUIT_BREAKER_RECOVERY_SECONDS
        )
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def allow_request(self):
        """Return True if the request should proceed."""
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_seconds:
                self.state = self.HALF_OPEN
                logging.info(
                    "CircuitBreaker[%s]: transitioning to HALF_OPEN", self.name
                )
                return True
            return False
        # HALF_OPEN: allow one probe
        return True

    def record_success(self):
        """Record a successful call."""
        if self.state == self.HALF_OPEN:
            logging.info("CircuitBreaker[%s]: recovery confirmed, closing", self.name)
        self.failure_count = 0
        self.state = self.CLOSED

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logging.warning(
                "CircuitBreaker[%s]: OPEN after %d failures",
                self.name,
                self.failure_count,
            )

    def is_open(self):
        return self.state == self.OPEN


def retry_with_backoff(
    fn,
    max_attempts=None,
    base_delay=None,
    max_delay=None,
    backoff_multiplier=None,
    transient_exceptions=None,
    circuit_breaker=None,
):
    """Call fn() with exponential backoff on transient failures.

    Args:
        fn: Callable to execute.
        max_attempts: Maximum number of attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        backoff_multiplier: Multiplier for each subsequent delay.
        transient_exceptions: Tuple of exception types to retry on.
        circuit_breaker: Optional CircuitBreaker instance.

    Returns:
        The return value of fn().

    Raises:
        The last exception if all retries are exhausted, or
        CircuitBreakerOpenError if the circuit breaker is open.
    """
    max_attempts = max_attempts or config.RETRY_MAX_ATTEMPTS
    base_delay = base_delay or config.RETRY_BASE_DELAY_SECONDS
    max_delay = max_delay or config.RETRY_MAX_DELAY_SECONDS
    backoff_multiplier = backoff_multiplier or config.RETRY_BACKOFF_MULTIPLIER
    transient_exceptions = transient_exceptions or config.TRANSIENT_EXCEPTIONS

    delay = base_delay
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        if circuit_breaker and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open"
            )

        try:
            result = fn()
            if circuit_breaker:
                circuit_breaker.record_success()
            return result
        except transient_exceptions as exc:
            last_exc = exc
            if circuit_breaker:
                circuit_breaker.record_failure()
            if attempt < max_attempts:
                logging.warning(
                    "Retry %d/%d failed (%s), sleeping %.1fs",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
            else:
                logging.error("All %d retries exhausted: %s", max_attempts, exc)
        except Exception as exc:
            # Non-transient exception — fail immediately
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise

    raise last_exc


class CircuitBreakerOpenError(Exception):
    """Raised when a call is blocked by an open circuit breaker."""
