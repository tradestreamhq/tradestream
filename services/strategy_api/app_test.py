"""Tests for the Strategy Derivation REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.strategy_api.app import create_app


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

    # Make pool.acquire() work as async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    # Disable auth for testing
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-api"


class TestSpecEndpoints:
    def test_list_specs(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=spec_id,
                name="macd",
                indicators={"macd": {}},
                entry_conditions={},
                exit_conditions={},
                parameters={},
                description="MACD strategy",
                source="MIGRATED",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/specs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "strategy_spec"

    def test_get_spec_found(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="rsi",
            indicators={"rsi": {}},
            entry_conditions={},
            exit_conditions={},
            parameters={},
            description="RSI",
            source="MIGRATED",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/specs/{spec_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "rsi"

    def test_get_spec_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/specs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_create_spec(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=spec_id,
            name="new_spec",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/specs",
            json={
                "name": "new_spec",
                "indicators": {"rsi": {"period": 14}},
                "entry_conditions": {"rsi_below": 30},
                "exit_conditions": {"rsi_above": 70},
                "parameters": {"period": {"min": 5, "max": 30}},
                "description": "Test spec",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(spec_id)

    def test_create_spec_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/specs", json={"name": "incomplete"})
        assert resp.status_code == 422

    def test_delete_spec(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=spec_id)

        resp = tc.delete(f"/specs/{spec_id}")
        assert resp.status_code == 204

    def test_delete_spec_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/specs/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestImplementationEndpoints:
    def test_list_implementations(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        spec_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=impl_id,
                spec_id=spec_id,
                parameters={},
                status="VALIDATED",
                optimization_method="GA",
                backtest_metrics={"sharpe_ratio": 1.5},
                paper_metrics=None,
                live_metrics=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/implementations")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_implementation_found(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=impl_id,
            spec_id=uuid.uuid4(),
            parameters={},
            status="VALIDATED",
            optimization_method="GA",
            backtest_metrics={"sharpe_ratio": 1.5},
            paper_metrics=None,
            live_metrics=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/implementations/{impl_id}")
        assert resp.status_code == 200

    def test_get_implementation_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/implementations/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_deactivate_implementation(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=impl_id)

        resp = tc.delete(f"/implementations/{impl_id}")
        assert resp.status_code == 204

    def test_evaluate_implementation(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=impl_id)

        resp = tc.post(
            f"/implementations/{impl_id}/evaluate",
            json={
                "instrument": "BTC/USD",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "SUBMITTED"
