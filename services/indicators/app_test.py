"""Tests for the Indicators REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.indicators.app import create_app


def _sample_candles(n: int = 30):
    return [
        {
            "time": f"2026-01-01T{i:02d}:00:00Z",
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0,
        }
        for i in range(n)
    ]


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


class TestGetIndicators:
    def test_default_indicators(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles()

        resp = tc.get("/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["pair"] == "BTC/USD"
        assert "sma" in attrs["indicators"]
        assert "ema" in attrs["indicators"]
        assert "rsi" in attrs["indicators"]
        assert len(attrs["indicators"]["sma"]) == 30

    def test_single_indicator(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles()

        resp = tc.get("/BTC%2FUSD?indicators=sma&sma_period=5")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "sma" in attrs["indicators"]
        # First 4 should be None with period=5
        assert attrs["indicators"]["sma"][:4] == [None, None, None, None]
        assert attrs["indicators"]["sma"][4] is not None

    def test_all_indicators(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles(50)

        resp = tc.get(
            "/BTC%2FUSD?indicators=sma,ema,rsi,macd,bollinger_bands,atr,vwap,stochastic"
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        for name in ["sma", "ema", "rsi", "macd", "bollinger_bands", "atr", "vwap", "stochastic"]:
            assert name in attrs["indicators"]

    def test_invalid_indicator(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles()

        resp = tc.get("/BTC%2FUSD?indicators=invalid_ind")
        assert resp.status_code == 422

    def test_no_candle_data(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/BTC%2FUSD")
        assert resp.status_code == 404

    def test_custom_params(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles()

        resp = tc.get(
            "/ETH%2FUSD?indicators=sma,rsi&sma_period=10&rsi_period=7&interval=4h&limit=50"
        )
        assert resp.status_code == 200
        influxdb.get_candles.assert_called_once_with(
            symbol="ETH/USD", timeframe="4h", start=None, limit=50
        )

    def test_macd_result_format(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles(40)

        resp = tc.get("/BTC%2FUSD?indicators=macd")
        assert resp.status_code == 200
        body = resp.json()
        macd_values = body["data"]["attributes"]["indicators"]["macd"]
        # Find first non-None MACD
        non_none = [v for v in macd_values if v is not None and v.get("macd") is not None]
        assert len(non_none) > 0
        assert "macd" in non_none[0]
        assert "signal" in non_none[0]
        assert "histogram" in non_none[0]

    def test_bollinger_bands_format(self, client):
        tc, influxdb = client
        influxdb.get_candles.return_value = _sample_candles(25)

        resp = tc.get("/BTC%2FUSD?indicators=bollinger_bands")
        assert resp.status_code == 200
        body = resp.json()
        bb_values = body["data"]["attributes"]["indicators"]["bollinger_bands"]
        non_none = [v for v in bb_values if v is not None and v.get("middle") is not None]
        assert len(non_none) > 0
        assert "upper" in non_none[0]
        assert "middle" in non_none[0]
        assert "lower" in non_none[0]
