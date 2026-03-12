"""Tests for the Strategy Versioning REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_versioning_api.app import create_app


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


# --- Health ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-versioning-api"


# --- List Versions ---


class TestListVersions:
    def test_list_versions(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        version_id = uuid.uuid4()

        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=version_id,
                strategy_id=strategy_id,
                version_number=1,
                parameters={"rsi_period": 14},
                indicators={"rsi": {}},
                entry_conditions={"rsi_below": 30},
                exit_conditions={"rsi_above": 70},
                changed_by="user1",
                changed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                change_reason="initial",
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/strategies/{strategy_id}/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "strategy_version"
        assert body["data"][0]["attributes"]["version_number"] == 1

    def test_list_versions_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/versions")
        assert resp.status_code == 404


# --- Get Version ---


class TestGetVersion:
    def test_get_version_found(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        version_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=version_id,
            strategy_id=strategy_id,
            version_number=2,
            parameters={"rsi_period": 21},
            indicators={"rsi": {}},
            entry_conditions={"rsi_below": 25},
            exit_conditions={"rsi_above": 75},
            changed_by="user1",
            changed_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
            change_reason="tuning",
        )

        resp = tc.get(f"/strategies/{strategy_id}/versions/2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version_number"] == 2
        assert body["data"]["attributes"]["parameters"]["rsi_period"] == 21

    def test_get_version_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/versions/99")
        assert resp.status_code == 404


# --- Diff Versions ---


class TestDiffVersions:
    def test_diff_shows_changes(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()

        row_a = FakeRecord(
            version_number=1,
            parameters={"rsi_period": 14},
            indicators={"rsi": {}},
            entry_conditions={"rsi_below": 30},
            exit_conditions={"rsi_above": 70},
        )
        row_b = FakeRecord(
            version_number=2,
            parameters={"rsi_period": 21},
            indicators={"rsi": {}},
            entry_conditions={"rsi_below": 25},
            exit_conditions={"rsi_above": 70},
        )
        conn.fetchrow.side_effect = [row_a, row_b]

        resp = tc.get(f"/strategies/{strategy_id}/versions/1/diff/2")
        assert resp.status_code == 200
        body = resp.json()
        changes = body["data"]["attributes"]["changes"]
        assert "parameters" in changes
        assert changes["parameters"]["before"]["rsi_period"] == 14
        assert changes["parameters"]["after"]["rsi_period"] == 21
        assert "entry_conditions" in changes
        # exit_conditions unchanged, should not appear
        assert "exit_conditions" not in changes
        # indicators unchanged, should not appear
        assert "indicators" not in changes

    def test_diff_version_a_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [None, FakeRecord(version_number=2, parameters={}, indicators={}, entry_conditions={}, exit_conditions={})]

        resp = tc.get(f"/strategies/{uuid.uuid4()}/versions/1/diff/2")
        assert resp.status_code == 404

    def test_diff_version_b_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(version_number=1, parameters={}, indicators={}, entry_conditions={}, exit_conditions={}),
            None,
        ]

        resp = tc.get(f"/strategies/{uuid.uuid4()}/versions/1/diff/2")
        assert resp.status_code == 404


# --- Rollback ---


class TestRollback:
    def test_rollback_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        new_version_id = uuid.uuid4()

        # Mock: target version exists
        target = FakeRecord(
            parameters={"rsi_period": 14},
            indicators={"rsi": {}},
            entry_conditions={"rsi_below": 30},
            exit_conditions={"rsi_above": 70},
        )
        conn.fetchrow.side_effect = [
            target,  # get target version
            FakeRecord(  # INSERT RETURNING
                id=new_version_id,
                strategy_id=strategy_id,
                version_number=3,
                parameters={"rsi_period": 14},
                indicators={"rsi": {}},
                entry_conditions={"rsi_below": 30},
                exit_conditions={"rsi_above": 70},
                changed_by="admin",
                changed_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
                change_reason="Rollback to version 1",
            ),
        ]
        conn.fetchval.return_value = 2  # current max version

        # Mock transaction context manager
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value = tx

        resp = tc.post(
            f"/strategies/{strategy_id}/rollback/1",
            json={"changed_by": "admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version_number"] == 3
        assert body["data"]["attributes"]["parameters"]["rsi_period"] == 14

    def test_rollback_version_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/rollback/99",
            json={"changed_by": "admin"},
        )
        assert resp.status_code == 404
