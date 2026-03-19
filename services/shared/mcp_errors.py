"""Structured error handling for MCP servers.

Provides standardized error codes and response formatting per the MCP servers spec.
"""

from typing import Any, Optional


# Standard error codes shared across all MCP servers
DATABASE_ERROR = "DATABASE_ERROR"
GRPC_ERROR = "GRPC_ERROR"
TIMEOUT = "TIMEOUT"
INVALID_PARAMETER = "INVALID_PARAMETER"
NOT_FOUND = "NOT_FOUND"
UNAUTHORIZED = "UNAUTHORIZED"

# Strategy-specific error codes
INVALID_SYMBOL = "INVALID_SYMBOL"
SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
SPEC_NOT_FOUND = "SPEC_NOT_FOUND"
NO_SIGNAL = "NO_SIGNAL"
NO_ACTIVE_STRATEGIES = "NO_ACTIVE_STRATEGIES"
INVALID_METRIC = "INVALID_METRIC"

# Market data error codes
INVALID_TIMEFRAME = "INVALID_TIMEFRAME"
NO_DATA = "NO_DATA"
STALE_DATA = "STALE_DATA"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Portfolio error codes
ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
INVALID_SIDE = "INVALID_SIDE"
INVALID_SIZE = "INVALID_SIZE"

# Backtest error codes
INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
BACKTEST_TIMEOUT = "BACKTEST_TIMEOUT"

# Decision error codes
INVALID_ACTION = "INVALID_ACTION"
INVALID_CONFIDENCE = "INVALID_CONFIDENCE"
REASONING_TOO_LONG = "REASONING_TOO_LONG"

# Strategy DB error codes
INVALID_SOURCE = "INVALID_SOURCE"
INVALID_STATUS = "INVALID_STATUS"
DUPLICATE_NAME = "DUPLICATE_NAME"
INVALID_INDICATORS = "INVALID_INDICATORS"
INVALID_CONDITIONS = "INVALID_CONDITIONS"
SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
INVALID_NAME = "INVALID_NAME"

# Web search error codes
SEARCH_FAILED = "SEARCH_FAILED"
RATE_LIMITED = "RATE_LIMITED"
INVALID_QUERY = "INVALID_QUERY"


class McpError(Exception):
    """Structured MCP error with code and details."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to the spec error response format."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


def error_response(
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
) -> dict[str, Any]:
    """Build a structured error response per spec."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    resp: dict[str, Any] = {"error": error}
    if latency_ms is not None:
        resp["_metadata"] = {"latency_ms": latency_ms}
    return resp
