"""Tests for the Market Data REST API."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.market_data_api.app import create_app


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


class TestInstruments:
    def test_list_instruments(self, client):
        tc, influxdb, redis = client
        redis.get_symbols.return_value = ["BTC/USD", "ETH/USD"]

        resp = tc.get("/instruments")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["symbol"] == "BTC/USD"

    def test_get_candles(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = [
            {
                "time": "2026-01-01T00:00:00Z",
                "open": 60000.0,
                "high": 61000.0,
                "low": 59000.0,
                "close": 60500.0,
                "volume": 100.0,
            }
        ]

        resp = tc.get("/instruments/BTC%2FUSD/candles?interval=1h")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_candles_missing_interval(self, client):
        tc, influxdb, redis = client
        resp = tc.get("/instruments/BTC%2FUSD/candles")
        assert resp.status_code == 422

    def test_get_candles_empty(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/instruments/BTC%2FUSD/candles?interval=1d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_price(self, client):
        tc, influxdb, redis = client
        influxdb.get_latest_price.return_value = {
            "symbol": "BTC/USD",
            "close": 60000.0,
            "time": "2026-01-01T00:00:00Z",
        }

        resp = tc.get("/instruments/BTC%2FUSD/price")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "BTC/USD"

    def test_get_price_not_found(self, client):
        tc, influxdb, redis = client
        influxdb.get_latest_price.return_value = None

        resp = tc.get("/instruments/INVALID/price")
        assert resp.status_code == 404

    def test_get_orderbook(self, client):
        tc, influxdb, redis = client
        resp = tc.get("/instruments/BTC%2FUSD/orderbook")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["symbol"] == "BTC/USD"


class TestCandleEndpoints:
    def test_get_candles_by_pair(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = [
            {
                "time": "2026-01-01T00:00:00Z",
                "open": 60000.0,
                "high": 61000.0,
                "low": 59000.0,
                "close": 60500.0,
                "volume": 100.0,
            }
        ]

        resp = tc.get("/candles/BTC%2FUSD?timeframe=1h")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_candles_by_pair_default_timeframe(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/candles/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_candles_by_pair_empty(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/candles/ETH%2FUSD?timeframe=5m")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_latest_candles(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = [
            {
                "time": "2026-01-01T00:05:00Z",
                "open": 60500.0,
                "high": 61000.0,
                "low": 60000.0,
                "close": 60800.0,
                "volume": 50.0,
            },
            {
                "time": "2026-01-01T00:00:00Z",
                "open": 60000.0,
                "high": 60500.0,
                "low": 59500.0,
                "close": 60500.0,
                "volume": 80.0,
            },
        ]

        resp = tc.get("/candles/BTC%2FUSD/latest?timeframe=5m&count=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_get_latest_candles_empty(self, client):
        tc, influxdb, redis = client
        influxdb.get_candles.return_value = []

        resp = tc.get("/candles/BTC%2FUSD/latest?timeframe=1h&count=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
