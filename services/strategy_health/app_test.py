"""Tests for the Strategy Health Checker API and checker logic."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_health.app import create_app
from services.strategy_health.checker import evaluate_health
from services.strategy_health.models import HealthState, MetricSnapshot


# ---------------------------------------------------------------------------
# Unit tests for the checker
# ---------------------------------------------------------------------------


class TestEvaluateHealth:
    def test_healthy_when_all_metrics_normal(self):
        metrics = MetricSnapshot(
            rolling_sharpe=1.5,
            sharpe_90d_avg=1.6,
            win_rate=0.55,
            win_rate_trend=-0.02,
            drawdown_depth=0.05,
            historical_max_drawdown=0.10,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.HEALTHY

    def test_degrading_when_sharpe_drops_30pct(self):
        metrics = MetricSnapshot(
            rolling_sharpe=0.65,
            sharpe_90d_avg=1.0,
            win_rate=0.55,
            win_rate_trend=0.0,
            drawdown_depth=0.05,
            historical_max_drawdown=0.10,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.DEGRADING
        assert any("Sharpe" in r for r in report.reasons)

    def test_critical_when_sharpe_drops_50pct(self):
        metrics = MetricSnapshot(
            rolling_sharpe=0.4,
            sharpe_90d_avg=1.0,
            win_rate=0.55,
            win_rate_trend=0.0,
            drawdown_depth=0.05,
            historical_max_drawdown=0.10,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.CRITICAL

    def test_critical_when_drawdown_exceeds_2x_max(self):
        metrics = MetricSnapshot(
            rolling_sharpe=1.5,
            sharpe_90d_avg=1.6,
            win_rate=0.55,
            win_rate_trend=0.0,
            drawdown_depth=0.25,
            historical_max_drawdown=0.10,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.CRITICAL
        assert any("Drawdown" in r for r in report.reasons)

    def test_degrading_when_win_rate_drops(self):
        metrics = MetricSnapshot(
            rolling_sharpe=1.5,
            sharpe_90d_avg=1.6,
            win_rate=0.40,
            win_rate_trend=-0.20,
            drawdown_depth=0.05,
            historical_max_drawdown=0.10,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.DEGRADING
        assert any("Win rate" in r for r in report.reasons)

    def test_disabled_state_preserved(self):
        metrics = MetricSnapshot(rolling_sharpe=0.1, sharpe_90d_avg=1.0)
        report = evaluate_health(
            "s1", metrics, "2026-01-01T00:00:00Z",
            previous_state=HealthState.DISABLED,
        )
        assert report.state == HealthState.DISABLED

    def test_healthy_with_no_metrics(self):
        metrics = MetricSnapshot()
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.HEALTHY

    def test_zero_historical_max_drawdown_no_division_error(self):
        metrics = MetricSnapshot(
            drawdown_depth=0.05,
            historical_max_drawdown=0.0,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.HEALTHY

    def test_zero_sharpe_90d_avg_no_division_error(self):
        metrics = MetricSnapshot(
            rolling_sharpe=0.5,
            sharpe_90d_avg=0.0,
        )
        report = evaluate_health("s1", metrics, "2026-01-01T00:00:00Z")
        assert report.state == HealthState.HEALTHY


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


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
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoint:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-health"


class TestGetStrategyHealth:
    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/{uuid.uuid4()}/health")
        assert resp.status_code == 404

    def test_healthy_strategy(self, client):
        tc, conn = client
        sid = str(uuid.uuid4())

        strategy_record = FakeRecord(id=sid, status="ACTIVE")
        sharpe_record = FakeRecord(rolling_sharpe=1.5, sharpe_90d_avg=1.6)
        win_rate_record = FakeRecord(current_win_rate=0.55, win_rate_trend=-0.02)
        drawdown_record = FakeRecord(
            current_drawdown=0.05, historical_max_drawdown=0.10
        )
        duration_record = FakeRecord(avg_duration_seconds=3600.0)

        conn.fetchrow.side_effect = [
            strategy_record,
            sharpe_record,
            win_rate_record,
            drawdown_record,
            duration_record,
        ]

        resp = tc.get(f"/{sid}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["state"] == "healthy"
        assert body["data"]["type"] == "strategy_health"

    def test_critical_strategy(self, client):
        tc, conn = client
        sid = str(uuid.uuid4())

        conn.fetchrow.side_effect = [
            FakeRecord(id=sid, status="ACTIVE"),
            FakeRecord(rolling_sharpe=0.3, sharpe_90d_avg=1.0),
            FakeRecord(current_win_rate=0.30, win_rate_trend=-0.25),
            FakeRecord(current_drawdown=0.30, historical_max_drawdown=0.10),
            FakeRecord(avg_duration_seconds=7200.0),
        ]

        resp = tc.get(f"/{sid}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["state"] == "critical"

    def test_disabled_strategy(self, client):
        tc, conn = client
        sid = str(uuid.uuid4())

        conn.fetchrow.side_effect = [
            FakeRecord(id=sid, status="DISABLED"),
            FakeRecord(rolling_sharpe=None, sharpe_90d_avg=None),
            FakeRecord(current_win_rate=None, win_rate_trend=None),
            FakeRecord(current_drawdown=None, historical_max_drawdown=None),
            FakeRecord(avg_duration_seconds=None),
        ]

        resp = tc.get(f"/{sid}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["state"] == "disabled"
