"""Tests for the Portfolio REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.portfolio_api.app import create_app


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


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestPortfolioState:
    def test_get_state(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.5,
                avg_entry_price=50000.0,
                unrealized_pnl=1000.0,
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchrow.return_value = FakeRecord(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            total_realized_pnl=5000.0,
        )

        resp = tc.get("/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["position_count"] == 1


class TestPositions:
    def test_list_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="ETH/USD",
                quantity=10.0,
                avg_entry_price=3000.0,
                unrealized_pnl=500.0,
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/positions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_position_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            symbol="BTC/USD",
            quantity=1.0,
            avg_entry_price=60000.0,
            unrealized_pnl=2000.0,
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get("/positions/BTC%2FUSD")
        assert resp.status_code == 200

    def test_get_position_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/positions/DOGE%2FUSD")
        assert resp.status_code == 404


class TestBalance:
    def test_get_balance(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(total_unrealized=1500.0),
            FakeRecord(total_realized=3000.0),
        ]

        resp = tc.get("/balance")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_equity"] == 4500.0


class TestRisk:
    def test_get_risk(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=1.0,
                avg_entry_price=60000.0,
                unrealized_pnl=0.0,
            )
        ]

        resp = tc.get("/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["position_count"] == 1


class TestValidation:
    def test_validate_buy(self, client):
        tc, conn = client
        resp = tc.post(
            "/validate",
            json={"instrument": "BTC/USD", "side": "BUY", "size": 0.1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is True

    def test_validate_sell_insufficient(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(quantity=0.05)

        resp = tc.post(
            "/validate",
            json={"instrument": "BTC/USD", "side": "SELL", "size": 1.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is False
        assert len(body["data"]["attributes"]["errors"]) > 0
