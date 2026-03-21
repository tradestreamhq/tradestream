"""Tests for the PnL Engine REST API endpoints."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.pnl_engine.app import create_app


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


def _trade(id, symbol, side, price, size, hour=1):
    return FakeRecord(
        id=id,
        symbol=symbol,
        side=side,
        price=Decimal(str(price)),
        size=Decimal(str(size)),
        executed_at=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
    )


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestRealizedPnL:
    def test_realized_fifo(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _trade(1, "BTC", "BUY", 100, 10, hour=1),
            _trade(2, "BTC", "BUY", 200, 10, hour=2),
            _trade(3, "BTC", "SELL", 150, 10, hour=3),
        ]
        resp = tc.get("/strat1/realized?method=fifo")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]
        assert len(items) >= 1
        # FIFO: sells against the $100 lot first
        pnl = items[0]["attributes"]["pnl"]
        assert pnl == 500.0  # (150-100)*10

    def test_realized_lifo(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _trade(1, "BTC", "BUY", 100, 10, hour=1),
            _trade(2, "BTC", "BUY", 200, 10, hour=2),
            _trade(3, "BTC", "SELL", 150, 10, hour=3),
        ]
        resp = tc.get("/strat1/realized?method=lifo")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]
        assert len(items) >= 1
        # LIFO: sells against the $200 lot first
        pnl = items[0]["attributes"]["pnl"]
        assert pnl == -500.0  # (150-200)*10

    def test_realized_average(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _trade(1, "BTC", "BUY", 100, 10, hour=1),
            _trade(2, "BTC", "BUY", 200, 10, hour=2),
            _trade(3, "BTC", "SELL", 150, 10, hour=3),
        ]
        resp = tc.get("/strat1/realized?method=average")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]
        assert len(items) >= 1
        # Average cost = 150, sell at 150 => PnL = 0
        pnl = items[0]["attributes"]["pnl"]
        assert pnl == 0.0

    def test_realized_no_trades(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/strat1/realized?method=fifo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []


class TestUnrealizedPnL:
    def test_unrealized_with_open_position(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # trades
            [
                _trade(1, "BTC", "BUY", 100, 10, hour=1),
                _trade(2, "BTC", "BUY", 200, 5, hour=2),
            ],
            # prices
            [FakeRecord(symbol="BTC", current_price=Decimal("180"))],
        ]
        resp = tc.get("/strat1/unrealized")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"]
        assert len(items) == 1
        attrs = items[0]["attributes"]
        assert attrs["symbol"] == "BTC"
        assert attrs["size"] == 15.0
        # (180-100)*10 + (180-200)*5 = 800 + (-100) = 700
        assert attrs["unrealized_pnl"] == 700.0

    def test_unrealized_no_trades(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]
        resp = tc.get("/strat1/unrealized")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestPnLSummary:
    def test_summary(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # trades
            [
                _trade(1, "BTC", "BUY", 100, 10, hour=1),
                _trade(2, "BTC", "SELL", 120, 5, hour=2),
            ],
            # prices
            [FakeRecord(symbol="BTC", current_price=Decimal("130"))],
        ]
        resp = tc.get("/strat1/summary?method=fifo")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_id"] == "strat1"
        assert attrs["method"] == "fifo"
        assert attrs["total_realized_pnl"] == 100.0  # (120-100)*5
        assert attrs["total_unrealized_pnl"] == 150.0  # (130-100)*5
        assert attrs["total_pnl"] == 250.0
        assert attrs["open_positions"] == 1
        assert attrs["closed_trades"] == 1

    def test_summary_no_trades(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]
        resp = tc.get("/strat1/summary?method=fifo")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_pnl"] == 0.0
