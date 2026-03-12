"""Tests for the Volatility Regime REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.volatility_regime.app import create_app


@pytest.fixture
def client():
    influxdb = MagicMock()
    app = create_app(influxdb)
    return TestClient(app, raise_server_exceptions=False), influxdb


class TestHealthEndpoints:
    def test_health(self, client):
        tc, influxdb = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ready(self, client):
        tc, influxdb = client
        resp = tc.get("/ready")
        assert resp.status_code == 200


class TestVolatilityRegimeEndpoint:
    def test_missing_symbol_param(self, client):
        tc, influxdb = client
        resp = tc.get("/volatility-regime")
        assert resp.status_code == 422

    def test_no_candle_data(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = []
        resp = tc.get("/volatility-regime?symbol=BTC/USD")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "INSUFFICIENT_DATA"

    def test_insufficient_prices(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = [
            {"close": 100.0},
            {"close": 101.0},
        ]
        resp = tc.get("/volatility-regime?symbol=BTC/USD")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INSUFFICIENT_DATA"

    def test_successful_classification(self, client):
        tc, influxdb = client
        # Generate 61 candles with stable prices → low volatility
        influxdb.get_candles.return_value = [
            {"close": 100.0 + i * 0.01} for i in range(61)
        ]
        resp = tc.get("/volatility-regime?symbol=BTC/USD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "volatility-regime"
        assert body["data"]["id"] == "BTC/USD"
        attrs = body["data"]["attributes"]
        assert attrs["regime"] in ["low", "medium", "high"]
        assert attrs["symbol"] == "BTC/USD"
        assert "volatility" in attrs
        assert "realized_vol_20d" in attrs["volatility"]
        assert "realized_vol_60d" in attrs["volatility"]

    def test_high_volatility_regime(self, client):
        tc, influxdb = client
        # Alternating prices → high volatility
        influxdb.get_candles.return_value = [
            {"close": 100.0 if i % 2 == 0 else 150.0} for i in range(61)
        ]
        resp = tc.get("/volatility-regime?symbol=ETH/USD")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["regime"] == "high"

    def test_data_fetch_error(self, client):
        tc, influxdb = client
        influxdb.get_candles.side_effect = Exception("connection refused")
        resp = tc.get("/volatility-regime?symbol=BTC/USD")
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "DATA_FETCH_ERROR"

    def test_candles_missing_close_field(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = [
            {"open": 100.0, "high": 101.0} for _ in range(30)
        ]
        resp = tc.get("/volatility-regime?symbol=BTC/USD")
        # No close values → insufficient data
        assert resp.status_code == 422
