"""Tests for the retry module."""

import time

import pytest

from services.autonomous_runner.retry import (
    RetryConfig,
    is_retryable_error,
    retry_with_backoff,
)


def test_successful_call_no_retry():
    call_count = 0

    def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = retry_with_backoff(succeed)
    assert result == "ok"
    assert call_count == 1


def test_retry_on_connection_error():
    call_count = 0

    def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("CONNECTION_ERROR: refused")
        return "recovered"

    config = RetryConfig(max_attempts=3, initial_delay_ms=10, max_delay_ms=50)
    result = retry_with_backoff(fail_then_succeed, config=config)
    assert result == "recovered"
    assert call_count == 3


def test_retry_exhausted_raises():
    def always_fail():
        raise TimeoutError("TIMEOUT: too slow")

    config = RetryConfig(max_attempts=2, initial_delay_ms=10)
    with pytest.raises(TimeoutError):
        retry_with_backoff(always_fail, config=config)


def test_non_retryable_error_no_retry():
    call_count = 0

    def fail_non_retryable():
        nonlocal call_count
        call_count += 1
        raise ValueError("INVALID_PARAMETERS: bad input")

    config = RetryConfig(max_attempts=3, initial_delay_ms=10)
    with pytest.raises(ValueError):
        retry_with_backoff(fail_non_retryable, config=config)
    assert call_count == 1


def test_on_retry_callback():
    attempts = []

    def fail_twice():
        if len(attempts) < 2:
            attempts.append(1)
            raise ConnectionError("CONNECTION_ERROR")
        return "done"

    retries = []
    config = RetryConfig(max_attempts=3, initial_delay_ms=10)
    result = retry_with_backoff(
        fail_twice, config=config, on_retry=lambda a, e, d: retries.append(a)
    )
    assert result == "done"
    assert retries == [1, 2]


def test_is_retryable_error():
    assert is_retryable_error(ConnectionError("CONNECTION_ERROR"))
    assert is_retryable_error(TimeoutError("TIMEOUT"))
    assert is_retryable_error(Exception("RATE_LIMITED"))
    assert is_retryable_error(Exception("SERVER_ERROR"))
    assert not is_retryable_error(ValueError("INVALID_PARAMETERS"))
    assert not is_retryable_error(ValueError("NOT_FOUND"))
    assert not is_retryable_error(PermissionError("UNAUTHORIZED"))


def test_backoff_increases_delay():
    delays = []

    def always_fail():
        raise ConnectionError("CONNECTION_ERROR")

    config = RetryConfig(
        max_attempts=3, initial_delay_ms=100, backoff_multiplier=2.0, jitter_pct=0
    )

    start = time.time()
    with pytest.raises(ConnectionError):
        retry_with_backoff(
            always_fail,
            config=config,
            on_retry=lambda a, e, d: delays.append(d),
        )
    elapsed = time.time() - start

    # Should have waited ~100ms + ~200ms = 300ms total
    assert elapsed >= 0.2  # at least 200ms
    assert len(delays) == 2
    assert delays[1] > delays[0]  # second delay is longer


def test_retry_with_args_and_kwargs():
    def add(a, b, offset=0):
        return a + b + offset

    result = retry_with_backoff(add, args=(1, 2), kwargs={"offset": 10})
    assert result == 13
