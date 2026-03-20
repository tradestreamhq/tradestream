"""Tests for the Market Scanner REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.market_scanner.app import create_app


@pytest.fixture
def client():
    market_data = MagicMock()
    app = create_app(market_data)
    return TestClient(app, raise_server_exceptions=False), market_data


class TestHealthEndpoints:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestCreateScan:
    def test_create_scan(self, client):
        tc, _ = client
        resp = tc.post(
            "/create",
            json={
                "pairs": ["BTC/USD", "ETH/USD"],
                "conditions": ["price_breakout", "volume_spike"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "scan"
        assert body["data"]["id"] is not None
        attrs = body["data"]["attributes"]
        assert attrs["pairs"] == ["BTC/USD", "ETH/USD"]
        assert "price_breakout" in attrs["conditions"]

    def test_create_scan_with_params(self, client):
        tc, _ = client
        resp = tc.post(
            "/create",
            json={
                "pairs": ["BTC/USD"],
                "conditions": ["rsi_extreme"],
                "params": {"rsi_overbought": 80, "rsi_oversold": 20},
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["params"]["rsi_overbought"] == 80

    def test_create_scan_empty_pairs(self, client):
        tc, _ = client
        resp = tc.post(
            "/create",
            json={"pairs": [], "conditions": ["price_breakout"]},
        )
        assert resp.status_code == 422

    def test_create_scan_empty_conditions(self, client):
        tc, _ = client
        resp = tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": []},
        )
        assert resp.status_code == 422

    def test_create_scan_invalid_condition(self, client):
        tc, _ = client
        resp = tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["invalid"]},
        )
        assert resp.status_code == 422


class TestDeleteScan:
    def test_delete_existing_scan(self, client):
        tc, _ = client
        create_resp = tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["price_breakout"]},
        )
        scan_id = create_resp.json()["data"]["id"]
        resp = tc.delete(f"/{scan_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["deleted"] is True

    def test_delete_nonexistent_scan(self, client):
        tc, _ = client
        resp = tc.delete("/nonexistent-id")
        assert resp.status_code == 404


class TestGetResults:
    def _make_candles(self, count=24, breakout=False, volume_spike=False):
        candles = []
        for i in range(count):
            candles.append(
                {
                    "time": f"2026-01-01T{i:02d}:00:00Z",
                    "open": 60000.0 + i * 10,
                    "high": 60100.0 + i * 10,
                    "low": 59900.0 + i * 10,
                    "close": 60050.0 + i * 10,
                    "volume": 100.0,
                }
            )
        if breakout:
            candles[-1]["close"] = 70000.0
            candles[-1]["high"] = 70000.0
        if volume_spike:
            candles[-1]["volume"] = 500.0
        return candles

    def test_results_empty(self, client):
        tc, market_data = client
        market_data.get_candles.return_value = []
        resp = tc.get("/results")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_results_with_breakout(self, client):
        tc, market_data = client
        candles = self._make_candles(breakout=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["price_breakout"]},
        )
        resp = tc.get("/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        result = data[0]["attributes"]
        assert result["pair"] == "BTC/USD"
        assert result["condition_met"] == "price_breakout"
        assert result["details"]["direction"] == "bullish"

    def test_results_with_volume_spike(self, client):
        tc, market_data = client
        candles = self._make_candles(volume_spike=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["volume_spike"]},
        )
        resp = tc.get("/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["attributes"]["condition_met"] == "volume_spike"

    def test_results_filter_by_pair(self, client):
        tc, market_data = client
        candles = self._make_candles(breakout=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={
                "pairs": ["BTC/USD", "ETH/USD"],
                "conditions": ["price_breakout"],
            },
        )
        resp = tc.get("/results?pair=BTC/USD")
        assert resp.status_code == 200
        for item in resp.json()["data"]:
            assert item["attributes"]["pair"] == "BTC/USD"

    def test_results_filter_by_condition(self, client):
        tc, market_data = client
        candles = self._make_candles(breakout=True, volume_spike=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={
                "pairs": ["BTC/USD"],
                "conditions": ["price_breakout", "volume_spike"],
            },
        )
        resp = tc.get("/results?condition=volume_spike")
        assert resp.status_code == 200
        for item in resp.json()["data"]:
            assert item["attributes"]["condition_met"] == "volume_spike"


class TestScannerRSI:
    def _make_rsi_candles(self, overbought=False):
        """Create candles that produce RSI extreme conditions."""
        closes = []
        base = 60000.0
        if overbought:
            for i in range(16):
                base += 100.0
                closes.append(base)
        else:
            for i in range(16):
                base -= 100.0
                closes.append(base)

        candles = []
        for i, close in enumerate(closes):
            candles.append(
                {
                    "time": f"2026-01-01T{i:02d}:00:00Z",
                    "open": close - 10,
                    "high": close + 10,
                    "low": close - 20,
                    "close": close,
                    "volume": 100.0,
                }
            )
        return candles

    def test_rsi_overbought(self, client):
        tc, market_data = client
        candles = self._make_rsi_candles(overbought=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["rsi_extreme"]},
        )
        resp = tc.get("/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["attributes"]["details"]["signal"] == "overbought"

    def test_rsi_oversold(self, client):
        tc, market_data = client
        candles = self._make_rsi_candles(overbought=False)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["rsi_extreme"]},
        )
        resp = tc.get("/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["attributes"]["details"]["signal"] == "oversold"


class TestScannerMACrossover:
    def _make_crossover_candles(self, bullish=True):
        """Create candles that produce MA crossover."""
        candles = []
        count = 22
        for i in range(count):
            if bullish:
                close = 60000.0 + (i * i * 5)
            else:
                close = 60000.0 - (i * i * 5)
            candles.append(
                {
                    "time": f"2026-01-01T{i:02d}:00:00Z",
                    "open": close - 10,
                    "high": close + 10,
                    "low": close - 20,
                    "close": close,
                    "volume": 100.0,
                }
            )
        return candles

    def test_ma_crossover_bullish(self, client):
        tc, market_data = client
        candles = self._make_crossover_candles(bullish=True)
        market_data.get_candles.return_value = candles

        tc.post(
            "/create",
            json={"pairs": ["BTC/USD"], "conditions": ["ma_crossover"]},
        )
        resp = tc.get("/results")
        assert resp.status_code == 200
