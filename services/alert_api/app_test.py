"""Tests for the Alert & Notification REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.alert_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    """Create a mock asyncpg pool with async context manager support."""
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
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "alert-api"


class TestCreateAlertRule:
    def test_create_success(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="High Drawdown",
            condition_type="drawdown_exceeded",
            threshold=10.0,
            strategy_id=None,
            implementation_id=None,
            notification_channels=["in_app"],
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/alerts",
            json={
                "name": "High Drawdown",
                "condition_type": "drawdown_exceeded",
                "threshold": 10.0,
                "notification_channels": ["in_app"],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(rule_id)
        assert body["data"]["type"] == "alert_rule"
        assert body["data"]["attributes"]["name"] == "High Drawdown"

    def test_create_invalid_condition_type(self, client):
        tc, conn = client
        resp = tc.post(
            "/alerts",
            json={
                "name": "Bad Rule",
                "condition_type": "invalid_type",
                "notification_channels": [],
            },
        )
        assert resp.status_code == 422

    def test_create_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/alerts", json={"name": "incomplete"})
        assert resp.status_code == 422


class TestListAlertRules:
    def test_list_rules(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=rule_id,
                name="PnL Target",
                condition_type="pnl_target",
                threshold=1000.0,
                strategy_id=None,
                implementation_id=None,
                notification_channels=["email"],
                is_active=True,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "alert_rule"

    def test_list_with_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/alerts?condition_type=pnl_target&active=true")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0


class TestGetAlertRule:
    def test_get_found(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="Signal Alert",
            condition_type="signal_generated",
            threshold=None,
            strategy_id=None,
            implementation_id=None,
            notification_channels=["in_app", "webhook"],
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/alerts/{rule_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["condition_type"] == "signal_generated"

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateAlertRule:
    def test_update_success(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="Updated Rule",
            condition_type="drawdown_exceeded",
            threshold=15.0,
            strategy_id=None,
            implementation_id=None,
            notification_channels=["in_app"],
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.put(
            f"/alerts/{rule_id}",
            json={"threshold": 15.0, "name": "Updated Rule"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["threshold"] == 15.0

    def test_update_no_fields(self, client):
        tc, conn = client
        resp = tc.put(f"/alerts/{uuid.uuid4()}", json={})
        assert resp.status_code == 422

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.put(f"/alerts/{uuid.uuid4()}", json={"name": "new"})
        assert resp.status_code == 404

    def test_update_invalid_condition_type(self, client):
        tc, conn = client
        resp = tc.put(
            f"/alerts/{uuid.uuid4()}",
            json={"condition_type": "invalid"},
        )
        assert resp.status_code == 422


class TestDeleteAlertRule:
    def test_delete_success(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=rule_id)

        resp = tc.delete(f"/alerts/{rule_id}")
        assert resp.status_code == 204

    def test_delete_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.delete(f"/alerts/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestAlertHistory:
    def test_get_history(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        history_id = uuid.uuid4()

        # First call: rule exists check, second call: history query
        conn.fetchrow.return_value = FakeRecord(id=rule_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=history_id,
                rule_id=rule_id,
                triggered_value=12.5,
                message="Drawdown 12.5% exceeded threshold 10%",
                metadata=None,
                acknowledged=False,
                acknowledged_at=None,
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/alerts/{rule_id}/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "alert_history"

    def test_get_history_rule_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/alerts/{uuid.uuid4()}/history")
        assert resp.status_code == 404
