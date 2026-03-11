"""Tests for the StructuredLogger shared library."""

import json
from unittest import mock

import pytest

from services.shared.structured_logger import (
    StructuredLogger,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


class TestStructuredLogger:
    """Tests for StructuredLogger JSON output."""

    def test_info_produces_json(self):
        logger = StructuredLogger(service_name="test_service", service_version="1.0")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("Server started", port=8080)
            mock_logging.info.assert_called_once()
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert entry["level"] == "INFO"
            assert entry["service"] == "test_service"
            assert entry["message"] == "Server started"
            assert entry["version"] == "1.0"
            assert entry["context"]["port"] == 8080

    def test_warning_level(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.warning("Low memory", available_mb=128)
            mock_logging.warning.assert_called_once()
            raw = mock_logging.warning.call_args[0][1]
            entry = json.loads(raw)
            assert entry["level"] == "WARNING"

    def test_error_level(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.error("Request failed", status=500)
            mock_logging.error.assert_called_once()
            raw = mock_logging.error.call_args[0][1]
            entry = json.loads(raw)
            assert entry["level"] == "ERROR"
            assert entry["context"]["status"] == 500

    def test_debug_level(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.debug("Trace data", key="val")
            mock_logging.debug.assert_called_once()
            raw = mock_logging.debug.call_args[0][1]
            entry = json.loads(raw)
            assert entry["level"] == "DEBUG"

    def test_no_context_when_no_kwargs(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("Simple message")
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert "context" not in entry

    def test_timestamp_present(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("msg")
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert "timestamp" in entry

    def test_service_version_from_env(self):
        with mock.patch.dict("os.environ", {"SERVICE_VERSION": "2.5.0"}):
            logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("msg")
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert entry["version"] == "2.5.0"


class TestCorrelationId:
    """Tests for correlation ID management."""

    def test_new_correlation_id_sets_and_returns(self):
        cid = new_correlation_id()
        assert len(cid) == 16
        assert get_correlation_id() == cid

    def test_set_correlation_id(self):
        set_correlation_id("custom-id-123")
        assert get_correlation_id() == "custom-id-123"

    def test_correlation_id_in_log_entry(self):
        logger = StructuredLogger(service_name="svc")
        set_correlation_id("req-abc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("With correlation")
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert entry["correlation_id"] == "req-abc"

    def test_no_correlation_id_when_empty(self):
        set_correlation_id("")
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.info("No correlation")
            raw = mock_logging.info.call_args[0][1]
            entry = json.loads(raw)
            assert "correlation_id" not in entry

    def test_logger_set_correlation_id(self):
        logger = StructuredLogger(service_name="svc")
        logger.set_correlation_id("from-logger")
        assert get_correlation_id() == "from-logger"

    def test_logger_new_correlation_id(self):
        logger = StructuredLogger(service_name="svc")
        cid = logger.new_correlation_id()
        assert len(cid) == 16
        assert get_correlation_id() == cid


class TestExceptionLogging:
    """Tests for exception logging."""

    def test_exception_calls_logging_exception(self):
        logger = StructuredLogger(service_name="svc")
        with mock.patch("services.shared.structured_logger.logging") as mock_logging:
            logger.exception("Something failed", error="timeout")
            mock_logging.exception.assert_called_once()
            raw = mock_logging.exception.call_args[0][1]
            entry = json.loads(raw)
            assert entry["level"] == "ERROR"
            assert entry["context"]["error"] == "timeout"
