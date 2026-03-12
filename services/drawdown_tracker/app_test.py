"""Tests for the Drawdown Tracker API and core tracker logic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.drawdown_tracker.app import create_app
from services.drawdown_tracker.models import DrawdownState
from services.drawdown_tracker.tracker import (
    build_drawdown_events,
    build_summary,
    compute_current_drawdown,
    estimate_recovery_days,
)


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


def _dt(day):
    return datetime(2026, 1, day, tzinfo=timezone.utc)


# --- Unit tests for tracker logic ---


class TestBuildDrawdownEvents:
    def test_no_drawdown(self):
        curve = [(_dt(1), 100), (_dt(2), 110), (_dt(3), 120)]
        events = build_drawdown_events(curve)
        assert events == []

    def test_single_recovered_drawdown(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 90),   # 10% drop
            (_dt(3), 85),   # trough: 15% drop
            (_dt(4), 95),
            (_dt(5), 100),  # recovered
        ]
        events = build_drawdown_events(curve)
        assert len(events) == 1
        assert events[0].state == DrawdownState.RECOVERED
        assert events[0].depth_pct == pytest.approx(15.0)
        assert events[0].recovery_date == _dt(5)

    def test_ongoing_drawdown(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 90),
            (_dt(3), 80),   # trough
            (_dt(4), 85),   # partial recovery
        ]
        events = build_drawdown_events(curve)
        assert len(events) == 1
        assert events[0].state == DrawdownState.RECOVERING
        assert events[0].recovery_date is None
        assert events[0].depth_pct == pytest.approx(20.0)

    def test_still_at_trough(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 90),
            (_dt(3), 80),
        ]
        events = build_drawdown_events(curve)
        assert len(events) == 1
        assert events[0].state == DrawdownState.IN_DRAWDOWN

    def test_multiple_drawdowns(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 90),
            (_dt(3), 100),  # recovered
            (_dt(4), 110),  # new peak
            (_dt(5), 95),   # new drawdown
            (_dt(6), 110),  # recovered
        ]
        events = build_drawdown_events(curve)
        assert len(events) == 2
        assert all(e.state == DrawdownState.RECOVERED for e in events)

    def test_ignores_shallow_drawdown(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 99.8),  # 0.2% — below threshold
            (_dt(3), 100),
        ]
        events = build_drawdown_events(curve, min_drawdown_pct=0.5)
        assert events == []

    def test_empty_curve(self):
        assert build_drawdown_events([]) == []

    def test_single_point(self):
        assert build_drawdown_events([(_dt(1), 100)]) == []


class TestComputeCurrentDrawdown:
    def test_at_peak(self):
        curve = [(_dt(1), 100), (_dt(2), 110)]
        events = build_drawdown_events(curve)
        current = compute_current_drawdown(curve, events)
        assert current.state == DrawdownState.AT_PEAK
        assert current.drawdown_pct == 0.0
        assert current.recovery_pct == 100.0

    def test_in_drawdown(self):
        curve = [(_dt(1), 100), (_dt(2), 80)]
        events = build_drawdown_events(curve)
        current = compute_current_drawdown(curve, events)
        assert current.state == DrawdownState.IN_DRAWDOWN
        assert current.drawdown_pct == pytest.approx(20.0)

    def test_recovering(self):
        curve = [(_dt(1), 100), (_dt(2), 80), (_dt(3), 90)]
        events = build_drawdown_events(curve)
        current = compute_current_drawdown(curve, events)
        assert current.state == DrawdownState.RECOVERING
        assert current.recovery_pct == pytest.approx(50.0)

    def test_empty_curve(self):
        current = compute_current_drawdown([], [])
        assert current.state == DrawdownState.AT_PEAK


class TestEstimateRecoveryDays:
    def test_already_recovered(self):
        from services.drawdown_tracker.models import DrawdownEvent

        event = DrawdownEvent(
            start_date=_dt(1),
            trough_date=_dt(3),
            recovery_date=None,
            peak_equity=100,
            trough_equity=80,
            depth_pct=20.0,
            duration_days=5,
            recovery_days=None,
            state=DrawdownState.RECOVERING,
        )
        result = estimate_recovery_days(event, 100.0, [(_dt(1), 100), (_dt(5), 100)], [])
        assert result == 0

    def test_trajectory_estimate(self):
        from services.drawdown_tracker.models import DrawdownEvent

        event = DrawdownEvent(
            start_date=_dt(1),
            trough_date=_dt(3),
            recovery_date=None,
            peak_equity=100,
            trough_equity=80,
            depth_pct=20.0,
            duration_days=10,
            recovery_days=None,
            state=DrawdownState.RECOVERING,
        )
        # Recovered 10 points in ~7 days, 10 more to go => ~7 more days
        curve = [(_dt(1), 100), (_dt(3), 80), (_dt(10), 90)]
        result = estimate_recovery_days(event, 90.0, curve, [event])
        assert result is not None
        assert result > 0


class TestBuildSummary:
    def test_full_summary(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 85),
            (_dt(3), 100),
            (_dt(4), 110),
            (_dt(5), 95),
            (_dt(6), 110),
        ]
        summary = build_summary("strat-abc", curve)
        assert summary.strategy_id == "strat-abc"
        assert summary.total_drawdown_events == 2
        assert summary.max_drawdown_pct == pytest.approx(15.0)
        assert summary.current.state == DrawdownState.AT_PEAK

    def test_summary_with_open_drawdown(self):
        curve = [
            (_dt(1), 100),
            (_dt(2), 80),
            (_dt(3), 85),
        ]
        summary = build_summary("strat-xyz", curve)
        assert summary.current.state == DrawdownState.RECOVERING
        assert summary.total_drawdown_events == 1


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestDrawdownEndpoint:
    def test_get_drawdowns_success(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(ts=datetime(2026, 1, 1), equity=0.0),
            FakeRecord(ts=datetime(2026, 1, 2), equity=-0.15),
            FakeRecord(ts=datetime(2026, 1, 3), equity=-0.05),
            FakeRecord(ts=datetime(2026, 1, 4), equity=0.10),
        ]

        resp = tc.get("/drawdowns/some-strategy-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "drawdown_summary"
        assert body["data"]["id"] == "some-strategy-id"
        attrs = body["data"]["attributes"]
        assert "current" in attrs
        assert "historical_events" in attrs
        assert attrs["strategy_id"] == "some-strategy-id"

    def test_get_drawdowns_not_found(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/drawdowns/missing-id")
        assert resp.status_code == 404

    def test_get_drawdowns_db_error(self, client):
        tc, conn = client
        conn.fetch.side_effect = Exception("connection refused")

        resp = tc.get("/drawdowns/some-id")
        assert resp.status_code == 500
