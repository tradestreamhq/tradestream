"""Tests for resilience utilities — retry with backoff and circuit breaker."""

import time
from unittest.mock import MagicMock, patch

from services.agent_orchestration.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    retry_with_backoff,
)


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_recovery_time(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_seconds=0.1)
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

        time.sleep(0.15)
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.HALF_OPEN

    def test_closes_on_success_after_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.failure_count == 0

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

    def test_is_open(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitBreaker.CLOSED


class TestRetryWithBackoff:
    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_succeeds_on_first_try(self, mock_sleep):
        fn = MagicMock(return_value="ok")
        result = retry_with_backoff(fn, max_attempts=3)
        assert result == "ok"
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_retries_on_transient_error(self, mock_sleep):
        fn = MagicMock(side_effect=[ConnectionError("fail"), "ok"])
        result = retry_with_backoff(fn, max_attempts=3, base_delay=0.1)
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once()

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_raises_after_all_retries_exhausted(self, mock_sleep):
        fn = MagicMock(side_effect=ConnectionError("fail"))
        try:
            retry_with_backoff(fn, max_attempts=3, base_delay=0.01)
            assert False, "Should have raised"
        except ConnectionError:
            pass
        assert fn.call_count == 3

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_does_not_retry_non_transient(self, mock_sleep):
        fn = MagicMock(side_effect=ValueError("bad input"))
        try:
            retry_with_backoff(fn, max_attempts=3)
            assert False, "Should have raised"
        except ValueError:
            pass
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        fn = MagicMock(
            side_effect=[ConnectionError(), ConnectionError(), "ok"]
        )
        retry_with_backoff(
            fn, max_attempts=3, base_delay=1.0, backoff_multiplier=2.0
        )
        assert mock_sleep.call_count == 2
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] == 1.0
        assert delays[1] == 2.0

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_respects_max_delay(self, mock_sleep):
        fn = MagicMock(
            side_effect=[ConnectionError(), ConnectionError(), "ok"]
        )
        retry_with_backoff(
            fn,
            max_attempts=3,
            base_delay=10.0,
            backoff_multiplier=2.0,
            max_delay=15.0,
        )
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[1] <= 15.0

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_circuit_breaker_blocks_when_open(self, mock_sleep):
        cb = CircuitBreaker("test", failure_threshold=1)
        cb.record_failure()  # opens the breaker

        fn = MagicMock(return_value="ok")
        try:
            retry_with_backoff(fn, circuit_breaker=cb)
            assert False, "Should have raised CircuitBreakerOpenError"
        except CircuitBreakerOpenError:
            pass
        fn.assert_not_called()

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_circuit_breaker_records_success(self, mock_sleep):
        cb = CircuitBreaker("test", failure_threshold=3)
        fn = MagicMock(return_value="ok")
        retry_with_backoff(fn, circuit_breaker=cb)
        assert cb.failure_count == 0

    @patch("services.agent_orchestration.resilience.time.sleep")
    def test_circuit_breaker_records_failure_on_transient(self, mock_sleep):
        cb = CircuitBreaker("test", failure_threshold=5)
        fn = MagicMock(side_effect=ConnectionError("fail"))
        try:
            retry_with_backoff(fn, max_attempts=2, base_delay=0.01, circuit_breaker=cb)
        except ConnectionError:
            pass
        assert cb.failure_count == 2
