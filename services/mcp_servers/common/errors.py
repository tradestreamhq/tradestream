"""Standardized error handling for MCP servers."""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass


class ErrorCode(str, Enum):
    """Standard error codes for MCP servers."""

    # Generic errors
    DATABASE_ERROR = "DATABASE_ERROR"
    GRPC_ERROR = "GRPC_ERROR"
    TIMEOUT = "TIMEOUT"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"

    # Strategy-specific errors
    INVALID_SYMBOL = "INVALID_SYMBOL"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    INVALID_METRIC = "INVALID_METRIC"
    STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
    NO_SIGNAL = "NO_SIGNAL"
    NO_ACTIVE_STRATEGIES = "NO_ACTIVE_STRATEGIES"

    # Market data errors
    INVALID_TIMEFRAME = "INVALID_TIMEFRAME"
    NO_DATA = "NO_DATA"
    STALE_DATA = "STALE_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

    # Portfolio errors
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    INVALID_SIDE = "INVALID_SIDE"
    INVALID_SIZE = "INVALID_SIZE"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"

    # Backtest errors
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    BACKTEST_TIMEOUT = "BACKTEST_TIMEOUT"

    # Decision errors
    INVALID_ACTION = "INVALID_ACTION"
    INVALID_CONFIDENCE = "INVALID_CONFIDENCE"
    REASONING_TOO_LONG = "REASONING_TOO_LONG"

    # Strategy DB errors
    INVALID_SOURCE = "INVALID_SOURCE"
    SPEC_NOT_FOUND = "SPEC_NOT_FOUND"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_NAME = "INVALID_NAME"
    DUPLICATE_NAME = "DUPLICATE_NAME"
    INVALID_INDICATORS = "INVALID_INDICATORS"
    INVALID_CONDITIONS = "INVALID_CONDITIONS"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    NO_PERFORMANCE_DATA = "NO_PERFORMANCE_DATA"
    INVALID_PERIOD = "INVALID_PERIOD"


@dataclass
class MCPError(Exception):
    """Structured error for MCP tool responses."""

    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        result = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


def error_response(error: MCPError, latency_ms: int) -> Dict[str, Any]:
    """Create a standardized error response."""
    return {
        "error": error.to_dict(),
        "_metadata": {"latency_ms": latency_ms},
    }
