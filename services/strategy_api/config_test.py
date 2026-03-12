"""Tests for strategy configuration versioning and rollback."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

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


STRATEGY_ID = str(uuid.uuid4())
CONFIG_ID = str(uuid.uuid4())
NOW = datetime(2026, 3, 12, tzinfo=timezone.utc)


def _spec_row():
    return FakeRecord(id=uuid.UUID(STRATEGY_ID))


def _config_row(version=1, is_active=True, params=None):
    return FakeRecord(
        id=uuid.UUID(CONFIG_ID),
        strategy_id=uuid.UUID(STRATEGY_ID),
        version=version,
        parameters=params or {"rsi_period": 14, "threshold": 30},
        description=f"Config v{version}",
        author="tester",
        is_active=is_active,
        created_at=NOW,
    )


class TestCreateConfig:
    def test_creates_first_version(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), _config_row(version=1)]
        conn.fetchval.return_value = 0  # no existing versions

        resp = tc.post(
            f"/strategies/{STRATEGY_ID}/config",
            json={
                "parameters": {"rsi_period": 14, "threshold": 30},
                "description": "Initial config",
                "author": "tester",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["version"] == 1
        assert body["data"]["attributes"]["is_active"] is True

    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/config",
            json={"parameters": {"rsi_period": 14}},
        )
        assert resp.status_code == 404

    def test_increments_version(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), _config_row(version=3)]
        conn.fetchval.return_value = 2  # two existing versions

        resp = tc.post(
            f"/strategies/{STRATEGY_ID}/config",
            json={"parameters": {"rsi_period": 21}},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["version"] == 3


class TestGetActiveConfig:
    def test_returns_active(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), _config_row(version=2)]

        resp = tc.get(f"/strategies/{STRATEGY_ID}/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version"] == 2
        assert body["data"]["attributes"]["is_active"] is True

    def test_no_active_config(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), None]

        resp = tc.get(f"/strategies/{STRATEGY_ID}/config")
        assert resp.status_code == 404

    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/config")
        assert resp.status_code == 404


class TestUpdateConfig:
    def test_partial_update_creates_new_version(self, client):
        tc, conn = client
        current = _config_row(version=1, params={"rsi_period": 14, "threshold": 30})
        updated = _config_row(version=2, params={"rsi_period": 14, "threshold": 25})
        conn.fetchrow.side_effect = [_spec_row(), current, updated]
        conn.fetchval.return_value = 1

        resp = tc.patch(
            f"/strategies/{STRATEGY_ID}/config",
            json={"parameters": {"threshold": 25}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version"] == 2

    def test_no_active_config_to_update(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), None]

        resp = tc.patch(
            f"/strategies/{STRATEGY_ID}/config",
            json={"parameters": {"threshold": 25}},
        )
        assert resp.status_code == 404


class TestConfigHistory:
    def test_returns_all_versions(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _spec_row()
        conn.fetch.return_value = [
            _config_row(version=2, is_active=True),
            _config_row(version=1, is_active=False),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get(f"/strategies/{STRATEGY_ID}/config/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["version"] == 2
        assert body["data"][1]["attributes"]["version"] == 1

    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/config/history")
        assert resp.status_code == 404


class TestRollbackConfig:
    def test_rollback_creates_new_version(self, client):
        tc, conn = client
        target = FakeRecord(
            parameters={"rsi_period": 14, "threshold": 30},
            description="Config v1",
            author="tester",
        )
        rolled_back = _config_row(version=3, params={"rsi_period": 14, "threshold": 30})
        conn.fetchrow.side_effect = [_spec_row(), target, rolled_back]
        conn.fetchval.return_value = 2  # current max version

        resp = tc.post(f"/strategies/{STRATEGY_ID}/config/rollback/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version"] == 3
        assert body["data"]["attributes"]["parameters"]["rsi_period"] == 14

    def test_rollback_version_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [_spec_row(), None]

        resp = tc.post(f"/strategies/{STRATEGY_ID}/config/rollback/99")
        assert resp.status_code == 404

    def test_rollback_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(f"/strategies/{uuid.uuid4()}/config/rollback/1")
        assert resp.status_code == 404


class TestVersioningIntegration:
    """Tests for versioning logic across multiple operations."""

    def test_only_one_active_config(self, client):
        """Creating a new config should deactivate the previous one."""
        tc, conn = client
        # First create
        conn.fetchrow.side_effect = [_spec_row(), _config_row(version=1)]
        conn.fetchval.return_value = 0

        resp1 = tc.post(
            f"/strategies/{STRATEGY_ID}/config",
            json={"parameters": {"rsi_period": 14}, "author": "tester"},
        )
        assert resp1.status_code == 201

        # Verify deactivation was called
        execute_calls = [
            c for c in conn.execute.call_args_list if "is_active = FALSE" in str(c)
        ]
        assert len(execute_calls) == 1

    def test_rollback_preserves_history(self, client):
        """Rollback creates a new version rather than deleting versions."""
        tc, conn = client
        target = FakeRecord(
            parameters={"rsi_period": 14},
            description="v1",
            author="tester",
        )
        rolled_back = _config_row(version=4, params={"rsi_period": 14})
        conn.fetchrow.side_effect = [_spec_row(), target, rolled_back]
        conn.fetchval.return_value = 3  # already at version 3

        resp = tc.post(f"/strategies/{STRATEGY_ID}/config/rollback/1")
        assert resp.status_code == 200
        body = resp.json()
        # New version is 4, not 1 — history is preserved
        assert body["data"]["attributes"]["version"] == 4
