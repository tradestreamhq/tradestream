"""Async circuit breaker for REST API external service calls.

Prevents cascading failures by tracking consecutive errors per service
and short-circuiting requests when a failure threshold is reached.

States:
- CLOSED: Normal operation, requests pass through.
- OPEN: Failure threshold reached, requests fail immediately.
- HALF_OPEN: Recovery period elapsed, next request is a probe.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for '{service_name}'. "
            f"Retry after {retry_after:.0f}s."
        )


class CircuitBreaker:
    """Async circuit breaker for protecting external service calls.

    Usage:
        cb = CircuitBreaker("postgres")
        result = await cb.call(some_async_fn, arg1, arg2)
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute fn through the circuit breaker.

        Args:
            fn: Async callable to execute.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            The return value of fn.

        Raises:
            CircuitOpenError: If the circuit is open.
            Exception: Any exception raised by fn.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            remaining = self.recovery_timeout - (
                time.monotonic() - self._last_failure_time
            )
            raise CircuitOpenError(self.service_name, max(0, remaining))

        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(self.service_name, self.recovery_timeout)
                self._half_open_calls += 1

        try:
            result = await fn(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._success_count += 1
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                logger.info(
                    "%s: circuit breaker closing after successful probe",
                    self.service_name,
                )
                self._state = CircuitState.CLOSED
                self._half_open_calls = 0

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "%s: half-open probe failed, re-opening circuit: %s",
                    self.service_name,
                    exc,
                )
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    "%s: circuit breaker OPEN after %d consecutive failures: %s",
                    self.service_name,
                    self._failure_count,
                    exc,
                )
                self._state = CircuitState.OPEN

    def to_dict(self) -> Dict[str, Any]:
        """Return circuit breaker metrics."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
