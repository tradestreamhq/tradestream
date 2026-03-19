"""Tests for MCP response metadata helpers."""

import json
import time

import pytest

from services.shared.mcp_metadata import wrap_response, wrap_error


class TestWrapResponse:
    def test_basic(self):
        start = time.monotonic()
        result = wrap_response(
            {"items": [1, 2, 3]},
            start_time=start,
            source="postgresql",
        )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["data"] == {"items": [1, 2, 3]}
        assert parsed["_metadata"]["cached"] is False
        assert parsed["_metadata"]["source"] == "postgresql"
        assert isinstance(parsed["_metadata"]["latency_ms"], int)
        assert parsed["_metadata"]["cache_ttl_remaining"] is None

    def test_cached(self):
        start = time.monotonic()
        result = wrap_response(
            {"value": "cached_data"},
            start_time=start,
            cached=True,
            cache_ttl_remaining=15.3,
            source="influxdb",
        )
        parsed = json.loads(result[0].text)
        assert parsed["_metadata"]["cached"] is True
        assert parsed["_metadata"]["cache_ttl_remaining"] == 15.3
        assert parsed["_metadata"]["source"] == "influxdb"


class TestWrapError:
    def test_basic(self):
        start = time.monotonic()
        result = wrap_error(
            {"code": "NOT_FOUND", "message": "missing"},
            start_time=start,
        )
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["error"]["code"] == "NOT_FOUND"
        assert isinstance(parsed["_metadata"]["latency_ms"], int)
