"""Tests for the async circuit breaker."""

import asyncio

import pytest

from services.rest_api_shared.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


@pytest.fixture
def breaker():
    return CircuitBreaker(
        "test-service", failure_threshold=3, recovery_timeout=1.0
    )


class TestCircuitBreakerClosed:
    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        async def ok():
            return "result"

        result = await breaker.call(ok)
        assert result == "result"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_single_failure_stays_closed(self, breaker):
        async def fail():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, breaker):
        async def fail():
            raise ConnectionError("down")

        async def ok():
            return "ok"

        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        with pytest.raises(ConnectionError):
            await breaker.call(fail)
        assert breaker.failure_count == 2

        await breaker.call(ok)
        assert breaker.failure_count == 0


class TestCircuitBreakerOpen:
    @pytest.mark.asyncio
    async def test_opens_after_threshold(self, breaker):
        async def fail():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_calls_when_open(self, breaker):
        async def fail():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail)

        with pytest.raises(CircuitOpenError) as exc_info:
            await breaker.call(fail)
        assert "test-service" in str(exc_info.value)
        assert exc_info.value.retry_after > 0


class TestCircuitBreakerHalfOpen:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self, breaker):
        breaker._failure_threshold = 1
        breaker._recovery_timeout = 0.0  # Immediately transition

        async def fail():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await breaker.call(fail)

        # Recovery timeout is 0, so state should be half-open
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes(self, breaker):
        breaker._recovery_timeout = 0.0

        async def fail():
            raise ConnectionError("down")

        async def ok():
            return "recovered"

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail)

        # Should be half-open now (recovery_timeout=0)
        result = await breaker.call(ok)
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens(self, breaker):
        breaker._recovery_timeout = 0.0

        async def fail():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail)

        # Half-open probe fails
        with pytest.raises(ConnectionError):
            await breaker.call(fail)

        # Should be open again
        assert breaker._state == CircuitState.OPEN


class TestCircuitBreakerMetrics:
    @pytest.mark.asyncio
    async def test_to_dict(self, breaker):
        metrics = breaker.to_dict()
        assert metrics["service"] == "test-service"
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 0
        assert metrics["failure_threshold"] == 3

    @pytest.mark.asyncio
    async def test_reset(self, breaker):
        async def fail():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
