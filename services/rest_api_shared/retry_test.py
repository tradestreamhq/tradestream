"""Tests for the async retry with exponential backoff."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.rest_api_shared.retry import is_transient, retry_with_backoff


class TestIsTransient:
    def test_connection_error(self):
        assert is_transient(ConnectionError("refused")) is True

    def test_timeout_error(self):
        assert is_transient(TimeoutError("timed out")) is True

    def test_os_error(self):
        assert is_transient(OSError("network")) is True

    def test_value_error_not_transient(self):
        assert is_transient(ValueError("bad value")) is False

    def test_key_error_not_transient(self):
        assert is_transient(KeyError("missing")) is False


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_backoff(fn, operation_name="test")
        assert result == "ok"
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_transient_error(self):
        fn = AsyncMock(side_effect=[ConnectionError("fail"), "ok"])
        with patch("services.rest_api_shared.retry.asyncio.sleep"):
            result = await retry_with_backoff(
                fn, max_attempts=3, operation_name="test"
            )
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_permanent_error_immediately(self):
        fn = AsyncMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError, match="bad"):
            await retry_with_backoff(fn, max_attempts=3, operation_name="test")
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        fn = AsyncMock(side_effect=ConnectionError("fail"))
        with patch("services.rest_api_shared.retry.asyncio.sleep"):
            with pytest.raises(ConnectionError, match="fail"):
                await retry_with_backoff(
                    fn, max_attempts=3, operation_name="test"
                )
        assert fn.call_count == 3

    @pytest.mark.asyncio
    async def test_custom_max_attempts(self):
        fn = AsyncMock(side_effect=TimeoutError("slow"))
        with patch("services.rest_api_shared.retry.asyncio.sleep"):
            with pytest.raises(TimeoutError):
                await retry_with_backoff(
                    fn, max_attempts=5, operation_name="test"
                )
        assert fn.call_count == 5

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        async def fn(a, b, key=None):
            return (a, b, key)

        result = await retry_with_backoff(
            fn, "x", "y", key="z", operation_name="test"
        )
        assert result == ("x", "y", "z")

    @pytest.mark.asyncio
    async def test_backoff_delay_increases(self):
        fn = AsyncMock(
            side_effect=[ConnectionError(), ConnectionError(), "ok"]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("services.rest_api_shared.retry.asyncio.sleep", side_effect=mock_sleep):
            await retry_with_backoff(
                fn,
                max_attempts=3,
                base_delay=1.0,
                backoff_multiplier=2.0,
                jitter=False,
                operation_name="test",
            )
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 1.0  # base_delay * 2^0
        assert sleep_calls[1] == 2.0  # base_delay * 2^1

    @pytest.mark.asyncio
    async def test_delay_capped_at_max(self):
        fn = AsyncMock(
            side_effect=[ConnectionError(), ConnectionError(), ConnectionError(), "ok"]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("services.rest_api_shared.retry.asyncio.sleep", side_effect=mock_sleep):
            await retry_with_backoff(
                fn,
                max_attempts=4,
                base_delay=10.0,
                max_delay=15.0,
                backoff_multiplier=2.0,
                jitter=False,
                operation_name="test",
            )
        # Third delay would be 10 * 2^2 = 40, but capped at 15
        assert sleep_calls[2] == 15.0
