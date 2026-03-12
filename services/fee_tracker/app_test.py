"""Tests for the Fee Analytics REST API."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.fee_tracker.app import create_app


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


class TestRecordFee:
    def test_record_fee(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=1,
            trade_id="t-001",
            strategy_id="strat-1",
            fee_type="commission",
            amount=2.50,
            currency="USD",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/",
            json={
                "trade_id": "t-001",
                "strategy_id": "strat-1",
                "fee_type": "commission",
                "amount": 2.50,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["trade_id"] == "t-001"
        assert body["data"]["attributes"]["amount"] == 2.50

    def test_record_fee_invalid_type(self, client):
        tc, _ = client
        resp = tc.post(
            "/",
            json={
                "trade_id": "t-001",
                "strategy_id": "strat-1",
                "fee_type": "invalid",
                "amount": 1.0,
            },
        )
        assert resp.status_code == 422


class TestListFees:
    def test_list_fees(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=1,
                trade_id="t-001",
                strategy_id="strat-1",
                fee_type="commission",
                amount=2.50,
                currency="USD",
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            FakeRecord(
                id=2,
                trade_id="t-002",
                strategy_id="strat-1",
                fee_type="exchange",
                amount=0.10,
                currency="USD",
                created_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_list_fees_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=1,
                trade_id="t-001",
                strategy_id="strat-1",
                fee_type="commission",
                amount=2.50,
                currency="USD",
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/?strategy_id=strat-1&fee_type=commission")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1


class TestFeeSummary:
    def test_summary(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                strategy_id="strat-1",
                fee_type="commission",
                fee_count=5,
                total_amount=12.50,
                currency="USD",
            ),
            FakeRecord(
                strategy_id="strat-1",
                fee_type="exchange",
                fee_count=3,
                total_amount=0.30,
                currency="USD",
            ),
        ]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        strategies = body["data"]["attributes"]["strategies"]
        assert len(strategies) == 2
        assert strategies[0]["total_amount"] == 12.50

    def test_summary_with_strategy_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/summary?strategy_id=strat-99")
        assert resp.status_code == 200


class TestFeeTrend:
    def test_trend(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                day=date(2026, 3, 1),
                total_fees=5.00,
                fee_count=3,
            ),
            FakeRecord(
                day=date(2026, 3, 2),
                total_fees=2.50,
                fee_count=2,
            ),
        ]

        resp = tc.get("/trend")
        assert resp.status_code == 200
        body = resp.json()
        trend = body["data"]["attributes"]["trend"]
        assert len(trend) == 2
        assert trend[0]["day"] == "2026-03-01"

    def test_trend_with_date_range(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/trend?start=2026-03-01T00:00:00Z&end=2026-03-31T23:59:59Z")
        assert resp.status_code == 200
