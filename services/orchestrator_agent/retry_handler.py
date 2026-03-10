"""Retry logic with exponential backoff and failure classification."""

import time

from absl import logging

from services.orchestrator_agent import config


def is_transient_error(exception):
    """Classify whether an exception is transient (retryable) or permanent.

    Transient errors include connection failures, timeouts, and OS-level
    network errors. Everything else is treated as permanent.
    """
    if isinstance(exception, config.TRANSIENT_EXCEPTIONS):
        return True
    # requests library exceptions
    try:
        import requests

        if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
            return True
    except ImportError:
        pass
    return False


def retry_with_backoff(fn, agent_name, max_attempts=None, base_delay=None):
    """Execute fn with exponential backoff retries for transient failures.

    Args:
        fn: Callable to execute. Should raise on failure.
        agent_name: Name of the agent (for logging).
        max_attempts: Max retry attempts (default from config).
        base_delay: Base delay in seconds (default from config).

    Returns:
        The return value of fn on success.

    Raises:
        The last exception if all retries are exhausted or a permanent error occurs.
    """
    if max_attempts is None:
        max_attempts = config.RETRY_MAX_ATTEMPTS
    if base_delay is None:
        base_delay = config.RETRY_BASE_DELAY_SECONDS

    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exception = e
            if not is_transient_error(e):
                logging.error("%s: permanent error (no retry): %s", agent_name, e)
                raise

            if attempt == max_attempts:
                logging.error(
                    "%s: transient error on final attempt %d/%d: %s",
                    agent_name,
                    attempt,
                    max_attempts,
                    e,
                )
                raise

            delay = min(
                base_delay * (config.RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)),
                config.RETRY_MAX_DELAY_SECONDS,
            )
            logging.warning(
                "%s: transient error (attempt %d/%d), retrying in %.1fs: %s",
                agent_name,
                attempt,
                max_attempts,
                delay,
                e,
            )
            time.sleep(delay)

    raise last_exception
