"""Tests for the Market Regime REST API endpoints."""

import math
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.market_regime.app import create_app
from services.market_regime.regime_detector import RegimeDetector


def _make_candles(n: int = 300, trend: str = "up"):
    """Generate synthetic candle dicts for API tests."""
    candles = []
    price = 100.0
    for i in range(n):
        if trend == "up":
            price *= 1.005
        elif trend == "down":
            price *= 0.995
        else:
            price = 100.0 + math.sin(i / 10.0)
        candles.append(
            {
                "time": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
                "open": price * 0.999,
                "high": price * 1.005,
                "low": price * 0.995,
                "close": price,
                "volume": 1000.0,
            }
        )
    return candles


@pytest.fixture
def client():
    influxdb = MagicMock()
    detector = RegimeDetector()
    app = create_app(influxdb, detector)
    return TestClient(app, raise_server_exceptions=False), influxdb, detector


class TestHealthEndpoints:
    def test_health(self, client):
        tc, influxdb, detector = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"


class TestRegimeEndpoint:
    def test_get_regime_trending_up(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(300, "up")

        resp = tc.get("/regime?symbol=BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["regime"] == "trending_up"
        assert body["data"]["attributes"]["confidence"] >= 0.5
        assert body["data"]["id"] == "BTC/USD"

    def test_get_regime_trending_down(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(300, "down")

        resp = tc.get("/regime?symbol=ETH%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["regime"] == "trending_down"

    def test_get_regime_no_data(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/regime?symbol=UNKNOWN")
        assert resp.status_code == 404

    def test_get_regime_insufficient_data(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(50, "up")

        resp = tc.get("/regime?symbol=BTC%2FUSD")
        assert resp.status_code == 422

    def test_get_regime_default_symbol(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(300, "up")

        resp = tc.get("/regime")
        assert resp.status_code == 200
        influxdb.get_candles.assert_called_with(
            symbol="BTC/USD", timeframe="1d", limit=300
        )

    def test_regime_includes_indicators(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(300, "up")

        resp = tc.get("/regime?symbol=BTC%2FUSD")
        body = resp.json()
        indicators = body["data"]["attributes"]["indicators"]
        assert "sma_20" in indicators
        assert "sma_50" in indicators
        assert "sma_200" in indicators
        assert "atr" in indicators
        assert "atr_percentile" in indicators
        assert "drawdown" in indicators
        assert "realized_volatility" in indicators


class TestRegimeHistoryEndpoint:
    def test_get_history_empty(self, client):
        tc, influxdb, detector = client
        resp = tc.get("/regime/history?symbol=BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_history_after_classification(self, client):
        tc, influxdb, detector = client
        influxdb.get_candles.return_value = _make_candles(300, "up")
        tc.get("/regime?symbol=BTC%2FUSD")

        resp = tc.get("/regime/history?symbol=BTC%2FUSD&days=90")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["regime"] == "trending_up"


class TestRegimeTransitionsEndpoint:
    def test_get_transitions_empty(self, client):
        tc, influxdb, detector = client
        resp = tc.get("/regime/transitions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_transitions_after_regime_change(self, client):
        tc, influxdb, detector = client
        # First call: trending up
        influxdb.get_candles.return_value = _make_candles(300, "up")
        tc.get("/regime?symbol=BTC%2FUSD")
        # Second call: trending down
        influxdb.get_candles.return_value = _make_candles(300, "down")
        tc.get("/regime?symbol=BTC%2FUSD")

        resp = tc.get("/regime/transitions?symbol=BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) >= 1
        t = body["data"][0]["attributes"]
        assert t["symbol"] == "BTC/USD"
        assert "previous_regime" in t
        assert "new_regime" in t
