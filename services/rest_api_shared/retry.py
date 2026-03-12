"""Async retry with exponential backoff for REST API service calls.

Provides configurable retry logic that classifies errors as transient
(retryable) or permanent, with jittered exponential backoff.
"""

import asyncio
import logging
import random
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

# Default transient exceptions that warrant retry
DEFAULT_TRANSIENT_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def is_transient(
    exc: BaseException,
    transient_types: Tuple[Type[BaseException], ...] = DEFAULT_TRANSIENT_EXCEPTIONS,
) -> bool:
    """Check if an exception is transient and should be retried."""
    if isinstance(exc, transient_types):
        return True
    # Check for common async library errors
    try:
        import asyncpg

        if isinstance(
            exc, (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError)
        ):
            return True
    except ImportError:
        pass
    try:
        import httpx

        if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout)):
            return True
    except ImportError:
        pass
    return False


async def retry_with_backoff(
    fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    transient_types: Tuple[Type[BaseException], ...] = DEFAULT_TRANSIENT_EXCEPTIONS,
    operation_name: str = "operation",
    **kwargs: Any,
) -> Any:
    """Execute an async callable with exponential backoff on transient failures.

    Args:
        fn: Async callable to execute.
        *args: Positional arguments for fn.
        max_attempts: Maximum number of attempts.
        base_delay: Base delay in seconds before first retry.
        max_delay: Maximum delay cap in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
        jitter: Whether to add random jitter to prevent thundering herd.
        transient_types: Exception types considered transient.
        operation_name: Name for logging.
        **kwargs: Keyword arguments for fn.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception if all retries are exhausted or a permanent error.
    """
    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc

            if not is_transient(exc, transient_types):
                logger.error("%s: permanent error (no retry): %s", operation_name, exc)
                raise

            if attempt == max_attempts:
                logger.error(
                    "%s: transient error on final attempt %d/%d: %s",
                    operation_name,
                    attempt,
                    max_attempts,
                    exc,
                )
                raise

            delay = min(
                base_delay * (backoff_multiplier ** (attempt - 1)),
                max_delay,
            )
            if jitter:
                delay = delay * (0.5 + random.random() * 0.5)

            logger.warning(
                "%s: transient error (attempt %d/%d), retrying in %.1fs: %s",
                operation_name,
                attempt,
                max_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
