"""Tests for the Portfolio Snapshot REST API."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.portfolio_snapshot.app import create_app


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
    return TestClient(app, raise_server_exceptions=False), conn, pool


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn, _ = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestCreateSnapshot:
    def test_create_snapshot(self, client):
        tc, _, pool = client

        snapshot_id = uuid.uuid4()

        with patch("services.portfolio_snapshot.app.capture_snapshot") as mock_capture:
            from services.portfolio_snapshot.models import (
                PortfolioSnapshot,
                SnapshotPosition,
            )

            mock_capture.return_value = PortfolioSnapshot(
                id=str(snapshot_id),
                snapshot_date=date(2026, 3, 12),
                total_equity=105000.0,
                cash_balance=0.0,
                margin_used=0.0,
                daily_change=5000.0,
                daily_change_pct=5.0,
                positions=[
                    SnapshotPosition(
                        symbol="BTC/USD", quantity=1.0, market_value=105000.0
                    )
                ],
            )

            resp = tc.post("/snapshots")
            assert resp.status_code == 201
            body = resp.json()
            assert body["data"]["type"] == "portfolio_snapshot"
            attrs = body["data"]["attributes"]
            assert attrs["total_equity"] == 105000.0
            assert attrs["daily_change"] == 5000.0
            assert len(attrs["positions"]) == 1
            assert attrs["positions"][0]["symbol"] == "BTC/USD"


class TestListSnapshots:
    def test_list_all(self, client):
        tc, conn, _ = client
        snapshot_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=snapshot_id,
                snapshot_date=date(2026, 3, 12),
                total_equity=Decimal("105000.0"),
                cash_balance=Decimal("0.0"),
                margin_used=Decimal("0.0"),
                daily_change=Decimal("5000.0"),
                daily_change_pct=Decimal("5.0"),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/snapshots")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["total_equity"] == 105000.0

    def test_list_with_date_range(self, client):
        tc, conn, _ = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/snapshots?start_date=2026-03-01&end_date=2026-03-12")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0


class TestGetSnapshot:
    def test_get_existing(self, client):
        tc, conn, _ = client
        snapshot_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=snapshot_id,
            snapshot_date=date(2026, 3, 12),
            total_equity=Decimal("105000.0"),
            cash_balance=Decimal("0.0"),
            margin_used=Decimal("0.0"),
            daily_change=Decimal("5000.0"),
            daily_change_pct=Decimal("5.0"),
        )
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=Decimal("1.0"),
                market_value=Decimal("105000.0"),
            )
        ]

        resp = tc.get("/snapshots/2026-03-12")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["snapshot_date"] == "2026-03-12"
        assert len(attrs["positions"]) == 1
        assert attrs["positions"][0]["symbol"] == "BTC/USD"

    def test_get_not_found(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = None

        resp = tc.get("/snapshots/2020-01-01")
        assert resp.status_code == 404


class TestSnapshotWithNullChange:
    def test_null_daily_change(self, client):
        tc, conn, _ = client
        snapshot_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=snapshot_id,
            snapshot_date=date(2026, 3, 12),
            total_equity=Decimal("100000.0"),
            cash_balance=Decimal("0.0"),
            margin_used=Decimal("0.0"),
            daily_change=None,
            daily_change_pct=None,
        )
        conn.fetch.return_value = []

        resp = tc.get("/snapshots/2026-03-12")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["daily_change"] is None
        assert attrs["daily_change_pct"] is None
