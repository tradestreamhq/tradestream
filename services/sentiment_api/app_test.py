"""Tests for the Sentiment Analysis REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.sentiment_api.app import create_app


def _make_candles(base=100, direction=1, count=40):
    """Generate test candle data."""
    return [
        {
            "time": f"2026-01-{i+1:02d}T00:00:00Z",
            "open": base + direction * i - 0.5,
            "high": base + direction * i + 1.0,
            "low": base + direction * i - 1.0,
            "close": base + direction * i,
            "volume": 100.0,
        }
        for i in range(count)
    ]


@pytest.fixture
def client():
    influxdb = MagicMock()
    redis = MagicMock()
    app = create_app(influxdb, redis)
    return TestClient(app, raise_server_exceptions=False), influxdb, redis


class TestHealthEndpoints:
    def test_health(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = ["BTC/USD"]
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestGetSentiment:
    def test_success(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = _make_candles()

        resp = tc.get("/?symbol=BTC/USD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "sentiment"
        assert body["data"]["id"] == "BTC/USD"
        attrs = body["data"]["attributes"]
        assert -1.0 <= attrs["score"] <= 1.0
        assert "breakdown" in attrs
        assert "timeframe_scores" in attrs

    def test_missing_symbol_param(self, client):
        tc, influxdb, redis = client
        resp = tc.get("/")
        assert resp.status_code == 422

    def test_no_data(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/?symbol=UNKNOWN")
        assert resp.status_code == 404

    def test_breakdown_fields(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = _make_candles()

        resp = tc.get("/?symbol=BTC/USD")
        body = resp.json()
        breakdown = body["data"]["attributes"]["breakdown"]
        assert "rsi" in breakdown
        assert "macd_trend" in breakdown
        assert "volume" in breakdown
        assert "price_momentum" in breakdown


class TestSentimentHistory:
    def test_success(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = _make_candles(count=70)

        resp = tc.get("/history?symbol=BTC/USD&timeframe=1d&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) > 0
        entry = body["data"][0]["attributes"]
        assert "timestamp" in entry
        assert "score" in entry
        assert "label" in entry

    def test_insufficient_data(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = _make_candles(count=10)

        resp = tc.get("/history?symbol=BTC/USD")
        assert resp.status_code == 404

    def test_invalid_timeframe(self, client):
        tc, influxdb, redis = client
        resp = tc.get("/history?symbol=BTC/USD&timeframe=3m")
        assert resp.status_code == 422


class TestDivergence:
    def test_returns_collection(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = ["BTC/USD"]
        influxdb.get_candles.return_value = _make_candles()

        resp = tc.get("/divergence")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body

    def test_empty_symbols(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = []

        resp = tc.get("/divergence")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestHeatmap:
    def test_returns_collection(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = ["BTC/USD", "ETH/USD"]
        influxdb.get_candles.return_value = _make_candles()

        resp = tc.get("/heatmap")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) > 0
        entry = body["data"][0]["attributes"]
        assert "symbol" in entry
        assert "score" in entry
        assert "label" in entry
        assert "color" in entry

    def test_empty_symbols(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = []

        resp = tc.get("/heatmap")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_color_format(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = ["BTC/USD"]
        influxdb.get_candles.return_value = _make_candles()

        resp = tc.get("/heatmap")
        body = resp.json()
        color = body["data"][0]["attributes"]["color"]
        assert color.startswith("#")
        assert len(color) == 7
