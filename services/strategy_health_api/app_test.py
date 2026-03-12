"""Tests for the Strategy Health Monitoring API."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_health_api.app import (
    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ERROR_RATE_DEGRADED,
    ERROR_RATE_UNHEALTHY,
    compute_health_status,
    create_app,
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
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


# ---------- Unit tests for compute_health_status ----------


class TestComputeHealthStatus:
    """Test health status derivation logic."""

    def test_no_heartbeat_returns_offline(self):
        assert compute_health_status(None, 0) == "offline"

    def test_recent_heartbeat_no_errors_healthy(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=30)
        assert compute_health_status(last, 0, now) == "healthy"

    def test_heartbeat_at_exact_timeout_is_healthy(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS)
        assert compute_health_status(last, 0, now) == "healthy"

    def test_heartbeat_past_timeout_is_offline(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS + 1)
        assert compute_health_status(last, 0, now) == "offline"

    def test_custom_timeout(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=61)
        assert compute_health_status(last, 0, now, timeout_seconds=60) == "offline"
        assert compute_health_status(last, 0, now, timeout_seconds=120) == "healthy"

    def test_errors_below_threshold_healthy(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_DEGRADED - 1, now) == "healthy"

    def test_errors_at_degraded_threshold(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_DEGRADED, now) == "degraded"

    def test_errors_between_degraded_and_unhealthy(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_DEGRADED + 3, now) == "degraded"

    def test_errors_at_unhealthy_threshold(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_UNHEALTHY, now) == "unhealthy"

    def test_errors_above_unhealthy_threshold(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_UNHEALTHY + 50, now) == "unhealthy"

    def test_offline_takes_priority_over_errors(self):
        """Even with high errors, if heartbeat is stale → offline."""
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS + 1)
        assert compute_health_status(last, ERROR_RATE_UNHEALTHY + 100, now) == "offline"

    def test_transition_healthy_to_degraded(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, 0, now) == "healthy"
        assert compute_health_status(last, ERROR_RATE_DEGRADED, now) == "degraded"

    def test_transition_degraded_to_unhealthy(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(seconds=10)
        assert compute_health_status(last, ERROR_RATE_DEGRADED, now) == "degraded"
        assert compute_health_status(last, ERROR_RATE_UNHEALTHY, now) == "unhealthy"

    def test_transition_healthy_to_offline(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(seconds=10)
        stale = now - timedelta(seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS + 1)
        assert compute_health_status(recent, 0, now) == "healthy"
        assert compute_health_status(stale, 0, now) == "offline"


# ---------- API endpoint tests ----------


class TestHealthEndpoints:
    def test_service_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-health-api"


class TestHeartbeatEndpoint:
    def test_heartbeat_new_strategy(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        check_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # No existing record
        conn.fetchrow.side_effect = [
            None,  # SELECT existing
            FakeRecord(  # UPSERT RETURNING
                id=check_id,
                strategy_id=strategy_id,
                status="healthy",
                last_heartbeat=now,
                uptime_pct=Decimal("100.00"),
                error_count=0,
                warning_count=0,
                last_error_msg=None,
                metadata={},
            ),
        ]
        conn.execute.return_value = None

        resp = tc.post(
            f"/strategies/{strategy_id}/heartbeat",
            json={},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "healthy"
        assert body["data"]["id"] == str(check_id)

    def test_heartbeat_with_errors(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        check_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        conn.fetchrow.side_effect = [
            FakeRecord(error_count=3),  # existing record
            FakeRecord(
                id=check_id,
                strategy_id=strategy_id,
                status="degraded",
                last_heartbeat=now,
                uptime_pct=Decimal("95.00"),
                error_count=8,
                warning_count=2,
                last_error_msg="Connection timeout",
                metadata={},
            ),
        ]
        conn.execute.return_value = None

        resp = tc.post(
            f"/strategies/{strategy_id}/heartbeat",
            json={
                "error_count": 5,
                "warning_count": 2,
                "error_message": "Connection timeout",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["error_count"] == 8

    def test_heartbeat_strategy_not_found(self, client):
        """Foreign key violation returns 404."""
        tc, conn = client
        import asyncpg

        conn.fetchrow.side_effect = [
            None,  # no existing record
            asyncpg.ForeignKeyViolationError(""),  # upsert fails
        ]

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/heartbeat",
            json={},
        )
        assert resp.status_code == 404


class TestGetAllHealth:
    def test_get_all_health_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_get_all_health_recomputes_offline(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        check_id = uuid.uuid4()
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)

        conn.fetch.return_value = [
            FakeRecord(
                id=check_id,
                strategy_id=strategy_id,
                status="healthy",  # stored as healthy, but heartbeat is stale
                last_heartbeat=stale_time,
                uptime_pct=Decimal("99.50"),
                error_count=0,
                warning_count=0,
                last_error_msg=None,
                metadata={},
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/strategies/health")
        assert resp.status_code == 200
        body = resp.json()
        # Should be recomputed to offline since heartbeat is 10 min old
        assert body["data"][0]["attributes"]["status"] == "offline"

    def test_get_all_health_multiple(self, client):
        tc, conn = client
        now = datetime.now(timezone.utc)

        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=uuid.uuid4(),
                status="healthy",
                last_heartbeat=now - timedelta(seconds=30),
                uptime_pct=Decimal("100.00"),
                error_count=0,
                warning_count=0,
                last_error_msg=None,
                metadata={},
            ),
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=uuid.uuid4(),
                status="degraded",
                last_heartbeat=now - timedelta(seconds=60),
                uptime_pct=Decimal("90.00"),
                error_count=10,
                warning_count=5,
                last_error_msg="Rate limited",
                metadata={},
            ),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get("/strategies/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2


class TestGetHealthHistory:
    def test_history_returns_entries(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=strategy_id,
                status="healthy",
                error_count=0,
                warning_count=0,
                last_error_msg=None,
                recorded_at=now,
            ),
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=strategy_id,
                status="degraded",
                error_count=7,
                warning_count=2,
                last_error_msg="Timeout",
                recorded_at=now - timedelta(minutes=5),
            ),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get(f"/strategies/{strategy_id}/health/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert body["data"][0]["attributes"]["status"] == "healthy"
        assert body["data"][1]["attributes"]["status"] == "degraded"

    def test_history_empty_but_strategy_exists(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = []
        conn.fetchval.side_effect = [0, 1]  # count=0, then exists=1

        resp = tc.get(f"/strategies/{strategy_id}/health/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_history_strategy_not_found(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = []
        conn.fetchval.side_effect = [0, None]  # count=0, exists=None

        resp = tc.get(f"/strategies/{strategy_id}/health/history")
        assert resp.status_code == 404
