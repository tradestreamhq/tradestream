"""Tests for the circuit breaker."""

import time
from unittest.mock import patch

import pytest

from services.shared.circuit_breaker import CircuitBreaker


class TestCircuitBreakerStates:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Simulate time passing
        cb._last_failure_time = time.time() - 2
        assert cb.state == "half_open"
        assert cb.allow_request() is True

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        cb._last_failure_time = time.time() - 2
        assert cb.state == "half_open"

        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        cb._last_failure_time = time.time() - 2

        # Allow one request through in half_open
        assert cb.allow_request() is True
        cb.record_failure()
        assert cb.state == "open"

    def test_half_open_limits_concurrent_calls(self):
        cb = CircuitBreaker(
            "test", failure_threshold=2, recovery_timeout=1, half_open_max_calls=1
        )
        cb.record_failure()
        cb.record_failure()
        cb._last_failure_time = time.time() - 2

        assert cb.allow_request() is True  # First call allowed
        assert cb.allow_request() is False  # Second blocked

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # After success, failure count should reset
        cb.record_failure()
        assert cb.state == "closed"

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request() is True


class TestCircuitBreakerToDict:
    def test_to_dict_structure(self):
        cb = CircuitBreaker("telegram-api", failure_threshold=5, recovery_timeout=30)
        d = cb.to_dict()
        assert d["name"] == "telegram-api"
        assert d["state"] == "closed"
        assert d["failure_count"] == 0
        assert d["success_count"] == 0
        assert d["failure_threshold"] == 5
        assert d["recovery_timeout"] == 30

    def test_to_dict_with_failures(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        d = cb.to_dict()
        assert d["state"] == "open"
        assert d["failure_count"] == 2
