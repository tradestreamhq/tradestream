"""Tests for the Performance Attribution REST API."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.performance_attribution.app import classify_asset_class, create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# --- Asset class classification ---


class TestClassifyAssetClass:
    def test_crypto_usd(self):
        assert classify_asset_class("BTC/USD") == "crypto"

    def test_crypto_usdt(self):
        assert classify_asset_class("ETH/USDT") == "crypto"

    def test_futures_perp(self):
        assert classify_asset_class("BTC-PERP") == "futures"

    def test_futures_fut(self):
        assert classify_asset_class("ES-FUT") == "futures"

    def test_equities(self):
        assert classify_asset_class("AAPL") == "equities"

    def test_case_insensitive(self):
        assert classify_asset_class("btc/usd") == "crypto"


# --- Health ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "performance-attribution"


# --- Strategy attribution ---


class TestStrategyAttribution:
    def test_pnl_by_strategy(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                strategy_name="RSI_Reversal",
                symbol="BTC/USD",
                pnl=Decimal("100.50"),
                opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            FakeRecord(
                strategy_name="RSI_Reversal",
                symbol="ETH/USD",
                pnl=Decimal("-30.00"),
                opened_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            ),
            FakeRecord(
                strategy_name="MACD_Cross",
                symbol="BTC/USD",
                pnl=Decimal("200.00"),
                opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/strategy")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        # MACD_Cross has higher PnL, should be first
        assert body["data"][0]["attributes"]["strategy_name"] == "MACD_Cross"
        assert body["data"][0]["attributes"]["total_pnl"] == 200.0
        assert body["data"][1]["attributes"]["strategy_name"] == "RSI_Reversal"
        assert body["data"][1]["attributes"]["win_rate"] == 0.5

    def test_pnl_by_strategy_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/strategy")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# --- Asset class attribution ---


class TestAssetClassAttribution:
    def test_pnl_by_asset_class(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                pnl=Decimal("100.00"),
                opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            FakeRecord(
                symbol="AAPL",
                pnl=Decimal("50.00"),
                opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/asset-class")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        classes = {d["attributes"]["asset_class"] for d in body["data"]}
        assert classes == {"crypto", "equities"}

    def test_pnl_by_asset_class_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/asset-class")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# --- Time attribution ---


class TestTimeAttribution:
    def test_pnl_by_time_daily(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                period=datetime(2026, 1, 1, tzinfo=timezone.utc),
                total_pnl=Decimal("150.00"),
                trade_count=5,
                winning_trades=3,
                losing_trades=2,
            ),
            FakeRecord(
                period=datetime(2026, 1, 2, tzinfo=timezone.utc),
                total_pnl=Decimal("-50.00"),
                trade_count=3,
                winning_trades=1,
                losing_trades=2,
            ),
        ]

        resp = tc.get("/time?bucket=daily")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        first = body["data"][0]["attributes"]
        assert first["bucket"] == "daily"
        assert first["total_pnl"] == 150.0
        assert first["win_rate"] == 0.6

    def test_pnl_by_time_weekly(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/time?bucket=weekly")
        assert resp.status_code == 200

    def test_pnl_by_time_monthly(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/time?bucket=monthly")
        assert resp.status_code == 200


# --- Summary ---


class TestSummary:
    def test_summary(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                pnl=Decimal("100.00"),
                symbol="BTC/USD",
                opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            FakeRecord(
                pnl=Decimal("-50.00"),
                symbol="ETH/USD",
                opened_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                closed_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_pnl"] == 50.0
        assert attrs["trade_count"] == 2
        assert attrs["win_rate"] == 0.5

    def test_summary_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/summary")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_pnl"] == 0
        assert attrs["trade_count"] == 0
        assert attrs["win_rate"] is None
