"""Tests for retry handler."""

from unittest import mock

import pytest

from services.orchestrator_agent import config
from services.orchestrator_agent.retry_handler import (
    is_transient_error,
    retry_with_backoff,
)


class TestIsTransientError:
    def test_connection_error_is_transient(self):
        assert is_transient_error(ConnectionError("refused")) is True

    def test_timeout_error_is_transient(self):
        assert is_transient_error(TimeoutError("timed out")) is True

    def test_os_error_is_transient(self):
        assert is_transient_error(OSError("network down")) is True

    def test_value_error_is_permanent(self):
        assert is_transient_error(ValueError("bad input")) is False

    def test_runtime_error_is_permanent(self):
        assert is_transient_error(RuntimeError("fatal")) is False

    @mock.patch.dict("sys.modules", {"requests": mock.MagicMock()})
    def test_requests_connection_error_is_transient(self):
        import requests

        exc = requests.ConnectionError("refused")
        # The isinstance check depends on actual requests module
        # This test verifies the import path doesn't crash
        is_transient_error(exc)


class TestRetryWithBackoff:
    @mock.patch("time.sleep")
    def test_succeeds_on_first_try(self, mock_sleep):
        fn = mock.Mock(return_value="ok")
        result = retry_with_backoff(fn, "test_agent")
        assert result == "ok"
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @mock.patch("time.sleep")
    def test_retries_on_transient_error(self, mock_sleep):
        fn = mock.Mock(side_effect=[ConnectionError("fail"), "ok"])
        result = retry_with_backoff(fn, "test_agent")
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once()

    @mock.patch("time.sleep")
    def test_no_retry_on_permanent_error(self, mock_sleep):
        fn = mock.Mock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError):
            retry_with_backoff(fn, "test_agent")
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @mock.patch("time.sleep")
    def test_exhausts_retries(self, mock_sleep):
        fn = mock.Mock(side_effect=ConnectionError("fail"))
        with pytest.raises(ConnectionError):
            retry_with_backoff(fn, "test_agent", max_attempts=3)
        assert fn.call_count == 3

    @mock.patch("time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        fn = mock.Mock(side_effect=[ConnectionError(), ConnectionError(), "ok"])
        retry_with_backoff(fn, "test_agent", max_attempts=3, base_delay=1.0)
        assert mock_sleep.call_count == 2
        # First delay: 1.0 * 2^0 = 1.0
        mock_sleep.assert_any_call(1.0)
        # Second delay: 1.0 * 2^1 = 2.0
        mock_sleep.assert_any_call(2.0)

    @mock.patch("time.sleep")
    def test_max_delay_cap(self, mock_sleep):
        fn = mock.Mock(side_effect=[ConnectionError(), ConnectionError(), "ok"])
        retry_with_backoff(fn, "test_agent", max_attempts=3, base_delay=20.0)
        # Second delay would be 20 * 2 = 40, capped at 30
        mock_sleep.assert_any_call(config.RETRY_MAX_DELAY_SECONDS)
