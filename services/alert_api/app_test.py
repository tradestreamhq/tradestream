"""Tests for the Alert Notification REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.alert_api.app import (
    create_app,
    evaluate_alert_condition,
    match_rules,
)


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
    return TestClient(app, raise_server_exceptions=False), conn


# --- Alert Evaluation Logic Tests ---


class TestEvaluateAlertCondition:
    def test_matching_type(self):
        assert evaluate_alert_condition(
            "signal_triggered", {}, {"type": "signal_triggered"}
        )

    def test_mismatched_type(self):
        assert not evaluate_alert_condition(
            "signal_triggered", {}, {"type": "position_opened"}
        )

    def test_min_confidence_pass(self):
        assert evaluate_alert_condition(
            "signal_triggered",
            {"min_confidence": 0.7},
            {"type": "signal_triggered", "confidence": 0.9},
        )

    def test_min_confidence_fail(self):
        assert not evaluate_alert_condition(
            "signal_triggered",
            {"min_confidence": 0.7},
            {"type": "signal_triggered", "confidence": 0.5},
        )

    def test_threshold_pass(self):
        assert evaluate_alert_condition(
            "risk_limit_breached",
            {"threshold": 100},
            {"type": "risk_limit_breached", "value": 150},
        )

    def test_threshold_fail(self):
        assert not evaluate_alert_condition(
            "risk_limit_breached",
            {"threshold": 100},
            {"type": "risk_limit_breached", "value": 50},
        )

    def test_symbols_filter_pass(self):
        assert evaluate_alert_condition(
            "signal_triggered",
            {"symbols": ["BTC-USD", "ETH-USD"]},
            {"type": "signal_triggered", "symbol": "BTC-USD"},
        )

    def test_symbols_filter_fail(self):
        assert not evaluate_alert_condition(
            "signal_triggered",
            {"symbols": ["BTC-USD"]},
            {"type": "signal_triggered", "symbol": "SOL-USD"},
        )

    def test_combined_conditions(self):
        assert evaluate_alert_condition(
            "signal_triggered",
            {"min_confidence": 0.5, "symbols": ["BTC-USD"]},
            {"type": "signal_triggered", "confidence": 0.8, "symbol": "BTC-USD"},
        )

    def test_combined_conditions_partial_fail(self):
        assert not evaluate_alert_condition(
            "signal_triggered",
            {"min_confidence": 0.9, "symbols": ["BTC-USD"]},
            {"type": "signal_triggered", "confidence": 0.5, "symbol": "BTC-USD"},
        )


class TestMatchRules:
    def test_matches_correct_rule(self):
        rules = [
            {
                "id": "r1",
                "alert_type": "signal_triggered",
                "conditions": {},
                "enabled": True,
            },
            {
                "id": "r2",
                "alert_type": "position_opened",
                "conditions": {},
                "enabled": True,
            },
        ]
        event = {"type": "signal_triggered", "strategy_id": "s1"}
        matched = match_rules(rules, event)
        assert len(matched) == 1
        assert matched[0]["id"] == "r1"

    def test_skips_disabled_rules(self):
        rules = [
            {
                "id": "r1",
                "alert_type": "signal_triggered",
                "conditions": {},
                "enabled": False,
            },
        ]
        event = {"type": "signal_triggered"}
        assert match_rules(rules, event) == []

    def test_strategy_scoping(self):
        rules = [
            {
                "id": "r1",
                "alert_type": "signal_triggered",
                "conditions": {},
                "enabled": True,
                "strategy_id": "strategy-abc",
            },
        ]
        event = {"type": "signal_triggered", "strategy_id": "strategy-xyz"}
        assert match_rules(rules, event) == []

        event2 = {"type": "signal_triggered", "strategy_id": "strategy-abc"}
        assert len(match_rules(rules, event2)) == 1

    def test_null_strategy_matches_all(self):
        rules = [
            {
                "id": "r1",
                "alert_type": "signal_triggered",
                "conditions": {},
                "enabled": True,
                "strategy_id": None,
            },
        ]
        event = {"type": "signal_triggered", "strategy_id": "any-strategy"}
        assert len(match_rules(rules, event)) == 1

    def test_multiple_matches(self):
        rules = [
            {
                "id": "r1",
                "alert_type": "signal_triggered",
                "conditions": {},
                "enabled": True,
            },
            {
                "id": "r2",
                "alert_type": "signal_triggered",
                "conditions": {"min_confidence": 0.5},
                "enabled": True,
            },
        ]
        event = {"type": "signal_triggered", "confidence": 0.8}
        assert len(match_rules(rules, event)) == 2


# --- Health Endpoint Tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "alert-api"


# --- Alert Rule CRUD Tests ---


class TestAlertRuleEndpoints:
    def test_create_rule(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="High confidence signal",
            strategy_id=None,
            alert_type="signal_triggered",
            conditions={"min_confidence": 0.8},
            enabled=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/rules",
            json={
                "name": "High confidence signal",
                "alert_type": "signal_triggered",
                "conditions": {"min_confidence": 0.8},
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(rule_id)
        assert body["data"]["attributes"]["alert_type"] == "signal_triggered"

    def test_create_rule_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/rules", json={"name": "incomplete"})
        assert resp.status_code == 422

    def test_list_rules(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=rule_id,
                name="SL alert",
                strategy_id=None,
                alert_type="stop_loss_hit",
                conditions={},
                enabled=True,
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "alert_rule"

    def test_get_rule_found(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="TP alert",
            strategy_id=None,
            alert_type="take_profit_hit",
            conditions={"threshold": 50},
            enabled=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/rules/{rule_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "TP alert"

    def test_get_rule_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/rules/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_rule(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=rule_id,
            name="Updated rule",
            strategy_id=None,
            alert_type="signal_triggered",
            conditions={"min_confidence": 0.9},
            enabled=False,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.patch(
            f"/rules/{rule_id}",
            json={"enabled": False, "conditions": {"min_confidence": 0.9}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["enabled"] is False

    def test_update_rule_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.patch(f"/rules/{uuid.uuid4()}", json={"enabled": False})
        assert resp.status_code == 404

    def test_update_rule_empty_body(self, client):
        tc, conn = client
        resp = tc.patch(f"/rules/{uuid.uuid4()}", json={})
        assert resp.status_code == 422

    def test_delete_rule(self, client):
        tc, conn = client
        rule_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=rule_id)
        resp = tc.delete(f"/rules/{rule_id}")
        assert resp.status_code == 204

    def test_delete_rule_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.delete(f"/rules/{uuid.uuid4()}")
        assert resp.status_code == 404


# --- Alert List/Status Tests ---


class TestAlertEndpoints:
    def test_list_alerts(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=alert_id,
                rule_id=rule_id,
                strategy_id=None,
                alert_type="signal_triggered",
                status="created",
                message="BTC signal triggered",
                details={"symbol": "BTC-USD"},
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["type"] == "alert"

    def test_list_alerts_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/?alert_type=stop_loss_hit&status=created")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_get_alert_found(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            rule_id=uuid.uuid4(),
            strategy_id=None,
            alert_type="position_closed",
            status="sent",
            message="Position closed",
            details={},
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/{alert_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "sent"

    def test_get_alert_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_alert_status(self, client):
        tc, conn = client
        alert_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=alert_id,
            rule_id=uuid.uuid4(),
            strategy_id=None,
            alert_type="signal_triggered",
            status="acknowledged",
            message="Signal alert",
            details={},
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.patch(f"/{alert_id}?status=acknowledged")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "acknowledged"

    def test_update_alert_status_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.patch(f"/{uuid.uuid4()}?status=dismissed")
        assert resp.status_code == 404
