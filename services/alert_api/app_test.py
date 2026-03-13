"""Tests for the Price Alert REST API."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.alert_api.app import _check_condition, create_app, run_evaluation


class FakeRecord(dict):
    """Dict subclass that mimics asyncpg.Record attribute access."""

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


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ------------------------------------------------------------------
# POST / — create alert
# ------------------------------------------------------------------


class TestCreateAlert:
    def test_create_absolute_alert(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            symbol="BTC/USD",
            condition="above",
            target_price=Decimal("70000"),
            reference_price=None,
            percentage=None,
            notification_channel="webhook",
            status="active",
            trigger_price=None,
            triggered_at=None,
            created_at=now,
            updated_at=now,
        )

        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "condition": "above",
                "target_price": 70000,
                "notification_channel": "webhook",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["symbol"] == "BTC/USD"
        assert body["data"]["attributes"]["status"] == "active"
        assert body["data"]["id"] == str(alert_id)

    def test_create_percentage_alert(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        # current_price=60000, percentage=5 => target=63000
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            symbol="ETH/USD",
            condition="above",
            target_price=Decimal("63000"),
            reference_price=Decimal("60000"),
            percentage=Decimal("5"),
            notification_channel="email",
            status="active",
            trigger_price=None,
            triggered_at=None,
            created_at=now,
            updated_at=now,
        )

        resp = tc.post(
            "",
            json={
                "symbol": "ETH/USD",
                "condition": "above",
                "percentage": 5.0,
                "current_price": 60000,
                "notification_channel": "email",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["percentage"] == 5.0
        assert body["data"]["attributes"]["reference_price"] == 60000.0

    def test_create_alert_missing_price_and_percentage(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "condition": "above",
            },
        )
        assert resp.status_code == 422

    def test_create_percentage_alert_missing_current_price(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "condition": "above",
                "percentage": 5.0,
            },
        )
        assert resp.status_code == 422

    def test_create_alert_invalid_condition(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "condition": "invalid",
                "target_price": 70000,
            },
        )
        assert resp.status_code == 422

    def test_create_alert_negative_target(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "symbol": "BTC/USD",
                "condition": "above",
                "target_price": -100,
            },
        )
        assert resp.status_code == 422


# ------------------------------------------------------------------
# GET / — list alerts
# ------------------------------------------------------------------


class TestListAlerts:
    def test_list_all_alerts(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="above",
                target_price=Decimal("70000"),
                reference_price=None,
                percentage=None,
                notification_channel="webhook",
                status="active",
                trigger_price=None,
                triggered_at=None,
                last_checked_price=None,
                created_at=now,
                updated_at=now,
            )
        ]

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "BTC/USD"

    def test_list_alerts_with_status_filter(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("", params={"status": "triggered"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_list_alerts_with_symbol_filter(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("", params={"symbol": "ETH/USD"})
        assert resp.status_code == 200


# ------------------------------------------------------------------
# DELETE /{alert_id} — cancel alert
# ------------------------------------------------------------------


class TestCancelAlert:
    def test_cancel_active_alert(self, client):
        tc, conn = client
        alert_id = str(uuid.uuid4())
        conn.fetchrow.return_value = FakeRecord(id=alert_id)

        resp = tc.delete(f"/{alert_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "cancelled"

    def test_cancel_nonexistent_alert(self, client):
        tc, conn = client
        alert_id = str(uuid.uuid4())
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{alert_id}")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# GET /history — triggered alerts
# ------------------------------------------------------------------


class TestAlertHistory:
    def test_history_returns_triggered(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="above",
                target_price=Decimal("70000"),
                reference_price=None,
                percentage=None,
                notification_channel="webhook",
                status="triggered",
                trigger_price=Decimal("70500"),
                triggered_at=now,
                created_at=now,
                updated_at=now,
            )
        ]

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["attributes"]["trigger_price"] == 70500.0

    def test_history_empty(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_history_with_symbol_filter(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("/history", params={"symbol": "ETH/USD"})
        assert resp.status_code == 200


# ------------------------------------------------------------------
# POST /evaluate — alert evaluation engine
# ------------------------------------------------------------------


class TestEvaluateAlerts:
    def test_evaluate_triggers_above(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="above",
                target_price=Decimal("70000"),
                last_checked_price=None,
            )
        ]
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            symbol="BTC/USD",
            condition="above",
            target_price=Decimal("70000"),
            trigger_price=Decimal("71000"),
            triggered_at=now,
            notification_channel="webhook",
        )

        resp = tc.post("/evaluate", json={"BTC/USD": 71000.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["triggered_count"] == 1

    def test_evaluate_no_trigger(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()

        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="above",
                target_price=Decimal("70000"),
                last_checked_price=None,
            )
        ]

        resp = tc.post("/evaluate", json={"BTC/USD": 69000.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["triggered_count"] == 0

    def test_evaluate_empty_prices(self, client):
        tc, conn = client
        resp = tc.post("/evaluate", json={})
        assert resp.status_code == 422


# ------------------------------------------------------------------
# _check_condition unit tests
# ------------------------------------------------------------------


class TestCheckCondition:
    def test_above_triggered(self):
        assert _check_condition("above", 100.0, 105.0, None) is True

    def test_above_exact(self):
        assert _check_condition("above", 100.0, 100.0, None) is True

    def test_above_not_triggered(self):
        assert _check_condition("above", 100.0, 95.0, None) is False

    def test_below_triggered(self):
        assert _check_condition("below", 100.0, 95.0, None) is True

    def test_below_exact(self):
        assert _check_condition("below", 100.0, 100.0, None) is True

    def test_below_not_triggered(self):
        assert _check_condition("below", 100.0, 105.0, None) is False

    def test_cross_up(self):
        assert _check_condition("cross", 100.0, 105.0, 95.0) is True

    def test_cross_down(self):
        assert _check_condition("cross", 100.0, 95.0, 105.0) is True

    def test_cross_no_last_price(self):
        assert _check_condition("cross", 100.0, 105.0, None) is False

    def test_cross_no_crossing(self):
        assert _check_condition("cross", 100.0, 105.0, 102.0) is False

    def test_cross_same_side(self):
        assert _check_condition("cross", 100.0, 95.0, 90.0) is False

    def test_unknown_condition(self):
        assert _check_condition("unknown", 100.0, 105.0, None) is False


# ------------------------------------------------------------------
# run_evaluation unit tests
# ------------------------------------------------------------------


class TestRunEvaluation:
    @pytest.mark.asyncio
    async def test_empty_prices(self):
        pool = AsyncMock()
        result = await run_evaluation(pool, {})
        assert result == []

    @pytest.mark.asyncio
    async def test_triggers_matching_alert(self):
        pool, conn = _make_pool()
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="below",
                target_price=Decimal("60000"),
                last_checked_price=None,
            )
        ]
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            symbol="BTC/USD",
            condition="below",
            target_price=Decimal("60000"),
            trigger_price=Decimal("59000"),
            triggered_at=now,
            notification_channel="webhook",
        )

        result = await run_evaluation(pool, {"BTC/USD": 59000.0})
        assert len(result) == 1
        assert result[0]["symbol"] == "BTC/USD"

    @pytest.mark.asyncio
    async def test_updates_last_checked_when_not_triggered(self):
        pool, conn = _make_pool()
        alert_id = uuid.uuid4()

        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="BTC/USD",
                condition="above",
                target_price=Decimal("70000"),
                last_checked_price=None,
            )
        ]

        result = await run_evaluation(pool, {"BTC/USD": 65000.0})
        assert len(result) == 0
        # Verify last_checked_price was updated
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cross_detection_with_history(self):
        pool, conn = _make_pool()
        alert_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)

        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                symbol="ETH/USD",
                condition="cross",
                target_price=Decimal("3000"),
                last_checked_price=Decimal("2900"),
            )
        ]
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            symbol="ETH/USD",
            condition="cross",
            target_price=Decimal("3000"),
            trigger_price=Decimal("3100"),
            triggered_at=now,
            notification_channel="slack",
        )

        result = await run_evaluation(pool, {"ETH/USD": 3100.0})
        assert len(result) == 1
