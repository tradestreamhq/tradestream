"""Tests for the Position Manager REST API."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.position_manager.app import create_app


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


def _open_position(**overrides):
    defaults = dict(
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        strategy_id="11111111-2222-3333-4444-555555555555",
        symbol="BTC/USD",
        side="LONG",
        entry_price=Decimal("50000"),
        quantity=Decimal("1.0"),
        stop_loss=Decimal("48000"),
        take_profit=Decimal("55000"),
        unrealized_pnl=Decimal("2000"),
        realized_pnl=None,
        status="OPEN",
        sizing_method="FIXED_FRACTION",
        opened_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        closed_at=None,
        close_reason=None,
        current_price=Decimal("52000"),
    )
    defaults.update(overrides)
    return FakeRecord(**defaults)


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestListPositions:
    def test_list_open_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = [_open_position()]

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "BTC/USD"

    def test_list_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0


class TestGetPosition:
    def test_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _open_position()

        resp = tc.get("/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["entry_price"] == 50000.0

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert resp.status_code == 404


class TestClosedHistory:
    def test_returns_closed_positions(self, client):
        tc, conn = client
        closed = _open_position(
            status="CLOSED",
            realized_pnl=Decimal("3000"),
            closed_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            close_reason="MANUAL",
        )
        conn.fetch.return_value = [closed]
        conn.fetchval.return_value = 1

        resp = tc.get("/history/closed")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1


class TestClosePosition:
    def test_close_open_position(self, client):
        tc, conn = client
        row = _open_position()
        closed_row = _open_position(
            status="CLOSED",
            realized_pnl=Decimal("5000"),
            closed_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            close_reason="MANUAL",
            unrealized_pnl=Decimal("0"),
            current_price=Decimal("55000"),
        )
        conn.fetchrow.side_effect = [row, closed_row]

        resp = tc.put(
            "/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/close",
            json={"exit_price": 55000.0, "reason": "MANUAL"},
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["status"] == "CLOSED"
        assert attrs["realized_pnl"] == 5000.0

    def test_close_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.put(
            "/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/close",
            json={"exit_price": 55000.0},
        )
        assert resp.status_code == 404

    def test_close_already_closed(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _open_position(status="CLOSED")

        resp = tc.put(
            "/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/close",
            json={"exit_price": 55000.0},
        )
        assert resp.status_code == 422
