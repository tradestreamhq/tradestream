"""Tests for MCP error utilities."""

import pytest

from services.shared.mcp_errors import (
    McpError,
    error_response,
    DATABASE_ERROR,
    STRATEGY_NOT_FOUND,
)


class TestMcpError:
    def test_to_dict_basic(self):
        err = McpError(STRATEGY_NOT_FOUND, "Strategy 'abc' not found")
        d = err.to_dict()
        assert d["code"] == "STRATEGY_NOT_FOUND"
        assert d["message"] == "Strategy 'abc' not found"
        assert "details" not in d

    def test_to_dict_with_details(self):
        err = McpError(
            DATABASE_ERROR,
            "Connection refused",
            details={"host": "localhost", "port": 5432},
        )
        d = err.to_dict()
        assert d["code"] == "DATABASE_ERROR"
        assert d["details"]["host"] == "localhost"

    def test_is_exception(self):
        err = McpError(DATABASE_ERROR, "fail")
        assert isinstance(err, Exception)
        assert str(err) == "fail"


class TestErrorResponse:
    def test_basic(self):
        resp = error_response(STRATEGY_NOT_FOUND, "Not found")
        assert resp["error"]["code"] == "STRATEGY_NOT_FOUND"
        assert "_metadata" not in resp

    def test_with_latency(self):
        resp = error_response(DATABASE_ERROR, "fail", latency_ms=42)
        assert resp["_metadata"]["latency_ms"] == 42

    def test_with_details(self):
        resp = error_response(
            STRATEGY_NOT_FOUND, "Not found", details={"id": "abc"}
        )
        assert resp["error"]["details"]["id"] == "abc"
