"""Tests for the Multi-Timeframe Analysis REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.mtf_analysis.app import create_app


def _make_candles(prices):
    return [
        {
            "timestamp": f"2026-01-01T00:{i:02d}:00Z",
            "open": p * 0.999,
            "high": p * 1.005,
            "low": p * 0.995,
            "close": p,
            "volume": 100.0,
        }
        for i, p in enumerate(prices)
    ]


def _uptrend(n=30, start=100.0):
    return [start + i for i in range(n)]


def _flat(n=30, price=100.0):
    return [price] * n


@pytest.fixture
def client():
    influxdb = MagicMock()
    app = create_app(influxdb)
    return TestClient(app, raise_server_exceptions=False), influxdb


class TestHealthEndpoints:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestSnapshotEndpoint:
    def test_snapshot_all_timeframes(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 6  # all 6 timeframes

    def test_snapshot_custom_timeframes(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD?timeframes=1h,4h")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_snapshot_invalid_timeframe(self, client):
        tc, influxdb = client
        resp = tc.get("/BTC%2FUSD?timeframes=2h")
        assert resp.status_code == 422

    def test_snapshot_returns_analysis_fields(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD?timeframes=1h")
        body = resp.json()
        item = body["data"][0]["attributes"]
        assert "timeframe" in item
        assert "signal" in item
        assert "strength" in item
        assert "indicators" in item
        assert "candle_count" in item

    def test_snapshot_influx_error(self, client):
        tc, influxdb = client
        influxdb.get_candles.side_effect = RuntimeError("connection failed")
        resp = tc.get("/BTC%2FUSD?timeframes=1h")
        assert resp.status_code == 404


class TestConfluenceEndpoint:
    def test_confluence_response(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD/confluence")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]["attributes"]
        assert "pair" in data
        assert "score" in data
        assert "signal" in data
        assert "agreeing_timeframes" in data
        assert "total_timeframes" in data

    def test_confluence_resource_id(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD/confluence")
        body = resp.json()
        assert body["data"]["id"] == "BTC/USD"

    def test_confluence_invalid_timeframe(self, client):
        tc, influxdb = client
        resp = tc.get("/BTC%2FUSD/confluence?timeframes=99d")
        assert resp.status_code == 422

    def test_confluence_custom_timeframes(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _make_candles(_uptrend(30))

        resp = tc.get("/BTC%2FUSD/confluence?timeframes=1h,4h,1d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["total_timeframes"] == 3

    def test_confluence_influx_error(self, client):
        tc, influxdb = client
        influxdb.get_candles.side_effect = RuntimeError("connection failed")
        resp = tc.get("/BTC%2FUSD/confluence")
        assert resp.status_code == 404
