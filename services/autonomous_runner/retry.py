"""Retry logic with exponential backoff for MCP tool calls.

Implements the spec-defined retry strategy:
- Max attempts: 3 (1 initial + 2 retries)
- Initial delay: 500ms
- Backoff multiplier: 2.0
- Max delay: 5000ms
- Jitter: 10%
"""

import logging
import random
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Retryable error types
RETRYABLE_ERRORS = {"TIMEOUT", "CONNECTION_ERROR", "RATE_LIMITED", "SERVER_ERROR"}
NON_RETRYABLE_ERRORS = {"INVALID_PARAMETERS", "NOT_FOUND", "UNAUTHORIZED"}


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: int = 500,
        max_delay_ms: int = 5000,
        backoff_multiplier: float = 2.0,
        jitter_pct: float = 0.10,
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.jitter_pct = jitter_pct


DEFAULT_RETRY_CONFIG = RetryConfig()


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable based on its type/message."""
    error_str = str(error).upper()
    for retryable in RETRYABLE_ERRORS:
        if retryable in error_str:
            return True
    for non_retryable in NON_RETRYABLE_ERRORS:
        if non_retryable in error_str:
            return False
    # Default: connection/timeout errors are retryable
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True
    return False


def retry_with_backoff(
    fn: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None,
) -> Any:
    """Execute a function with exponential backoff retry.

    Args:
        fn: The function to call.
        args: Positional arguments.
        kwargs: Keyword arguments.
        config: Retry configuration.
        on_retry: Callback called on each retry (attempt, error, delay_ms).

    Returns:
        The function's return value.

    Raises:
        The last exception if all retries are exhausted.
    """
    if kwargs is None:
        kwargs = {}
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    last_error = None
    delay_ms = config.initial_delay_ms

    for attempt in range(config.max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e

            if attempt == config.max_attempts - 1:
                break

            if not is_retryable_error(e):
                logger.debug("Non-retryable error: %s", e)
                break

            # Apply jitter
            jitter = delay_ms * config.jitter_pct * (2 * random.random() - 1)
            actual_delay_ms = delay_ms + jitter

            logger.info(
                "Retry %d/%d after %.0fms: %s",
                attempt + 1,
                config.max_attempts - 1,
                actual_delay_ms,
                e,
            )

            if on_retry:
                on_retry(attempt + 1, e, actual_delay_ms)

            time.sleep(actual_delay_ms / 1000.0)
            delay_ms = min(
                delay_ms * config.backoff_multiplier,
                config.max_delay_ms,
            )

    raise last_error
