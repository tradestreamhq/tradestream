"""Structured Logger - JSON structured logging with correlation IDs for TradeStream services.

Provides consistent JSON-formatted log output with:
- Correlation ID generation and propagation
- Service name and version metadata
- Structured key-value context in each log entry
- Thread-safe correlation ID management via contextvars
"""

import contextvars
import json
import logging as _stdlib_logging
import os
import time
import uuid

from absl import logging

# Thread-safe correlation ID storage.
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if none is set."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> contextvars.Token:
    """Set the correlation ID for the current context.

    Returns a token that can be used to reset the correlation ID.
    """
    return _correlation_id.set(cid)


def new_correlation_id() -> str:
    """Generate a new correlation ID, set it in context, and return it."""
    cid = uuid.uuid4().hex[:16]
    _correlation_id.set(cid)
    return cid


class StructuredLogger:
    """JSON structured logger wrapping absl.logging.

    Usage:
        logger = StructuredLogger(service_name="notification_service")

        # Basic logging
        logger.info("Server started", port=8080)
        logger.error("Request failed", error="timeout", endpoint="/api/data")

        # With correlation ID
        logger.set_correlation_id("abc123")
        logger.info("Processing request", user_id=42)
    """

    def __init__(self, service_name: str, service_version: str = ""):
        self._service_name = service_name
        self._service_version = service_version or os.environ.get(
            "SERVICE_VERSION", "unknown"
        )

    def _build_entry(self, level: str, message: str, **kwargs) -> str:
        """Build a JSON log entry."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
            "level": level,
            "service": self._service_name,
            "message": message,
        }

        cid = get_correlation_id()
        if cid:
            entry["correlation_id"] = cid

        if self._service_version:
            entry["version"] = self._service_version

        if kwargs:
            entry["context"] = kwargs

        return json.dumps(entry, default=str)

    def info(self, message: str, **kwargs):
        """Log at INFO level with structured context."""
        logging.info("%s", self._build_entry("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log at WARNING level with structured context."""
        logging.warning("%s", self._build_entry("WARNING", message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log at ERROR level with structured context."""
        logging.error("%s", self._build_entry("ERROR", message, **kwargs))

    def debug(self, message: str, **kwargs):
        """Log at DEBUG level with structured context."""
        logging.debug("%s", self._build_entry("DEBUG", message, **kwargs))

    def exception(self, message: str, **kwargs):
        """Log at ERROR level with exception info."""
        logging.exception("%s", self._build_entry("ERROR", message, **kwargs))

    def set_correlation_id(self, cid: str) -> contextvars.Token:
        """Set the correlation ID for the current context."""
        return set_correlation_id(cid)

    def new_correlation_id(self) -> str:
        """Generate and set a new correlation ID."""
        return new_correlation_id()
