"""Tests for the Strategy Scheduler REST API."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_scheduler.app import create_app


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


class TestGetSchedule:
    def test_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            strategy_id="aaaa-bbbb",
            active_hours_start="14:00",
            active_hours_end="20:00",
            market_phases=["regular"],
            cron_expression=None,
            timezone="UTC",
            enabled=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.get("/aaaa-bbbb/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["enabled"] is True
        assert body["data"]["attributes"]["active_hours_start"] == "14:00"

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/missing-id/schedule")
        assert resp.status_code == 404


class TestPutSchedule:
    def test_create(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            strategy_id="aaaa-bbbb",
            active_hours_start="09:00",
            active_hours_end="17:00",
            market_phases=["regular", "pre_market"],
            cron_expression="*/5 * * * *",
            timezone="UTC",
            enabled=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.put(
            "/aaaa-bbbb/schedule",
            json={
                "active_hours_start": "09:00",
                "active_hours_end": "17:00",
                "market_phases": ["regular", "pre_market"],
                "cron_expression": "*/5 * * * *",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["active_hours_start"] == "09:00"

    def test_invalid_cron(self, client):
        tc, conn = client
        resp = tc.put(
            "/aaaa-bbbb/schedule",
            json={
                "cron_expression": "not valid",
                "market_phases": ["regular"],
            },
        )
        assert resp.status_code == 422


class TestScheduleStatus:
    def test_status(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            strategy_id="aaaa-bbbb",
            active_hours_start=None,
            active_hours_end=None,
            market_phases=["regular"],
            cron_expression=None,
            timezone="UTC",
            enabled=True,
        )

        resp = tc.get("/aaaa-bbbb/schedule/status")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "should_run" in attrs
        assert "current_market_phase" in attrs

    def test_status_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/missing-id/schedule/status")
        assert resp.status_code == 404
