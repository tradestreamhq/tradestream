"""Tests for the Strategy Versioning and Audit Trail system."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from fastapi.testclient import TestClient

from services.strategy_api.app import create_app
from services.strategy_api.versioning import diff_configs


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


# --- diff_configs unit tests ---


class TestDiffConfigs:
    def test_no_changes(self):
        config = {"name": "rsi", "indicators": {"rsi": {"period": 14}}}
        assert diff_configs(config, config) == []

    def test_added_field(self):
        old = {"name": "rsi"}
        new = {"name": "rsi", "description": "RSI strategy"}
        changes = diff_configs(old, new)
        assert len(changes) == 1
        assert changes[0]["field"] == "description"
        assert changes[0]["action"] == "added"
        assert changes[0]["new_value"] == "RSI strategy"

    def test_removed_field(self):
        old = {"name": "rsi", "description": "RSI strategy"}
        new = {"name": "rsi"}
        changes = diff_configs(old, new)
        assert len(changes) == 1
        assert changes[0]["field"] == "description"
        assert changes[0]["action"] == "removed"
        assert changes[0]["old_value"] == "RSI strategy"

    def test_modified_field(self):
        old = {"name": "rsi", "description": "old"}
        new = {"name": "rsi", "description": "new"}
        changes = diff_configs(old, new)
        assert len(changes) == 1
        assert changes[0]["field"] == "description"
        assert changes[0]["action"] == "modified"
        assert changes[0]["old_value"] == "old"
        assert changes[0]["new_value"] == "new"

    def test_nested_changes(self):
        old = {"indicators": {"rsi": {"period": 14}}}
        new = {"indicators": {"rsi": {"period": 21}}}
        changes = diff_configs(old, new)
        assert len(changes) == 1
        assert changes[0]["field"] == "indicators.rsi.period"
        assert changes[0]["action"] == "modified"
        assert changes[0]["old_value"] == 14
        assert changes[0]["new_value"] == 21

    def test_multiple_changes(self):
        old = {"name": "rsi", "indicators": {"rsi": {"period": 14}}}
        new = {"name": "macd", "indicators": {"macd": {"fast": 12}}}
        changes = diff_configs(old, new)
        assert len(changes) >= 2  # name modified + indicator changes


# --- Versioning endpoint tests ---


class TestListVersions:
    def test_list_versions(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        version_id = uuid.uuid4()

        # First call: spec exists check
        conn.fetchrow.return_value = FakeRecord(id=spec_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=version_id,
                strategy_id=spec_id,
                version_number=1,
                config_snapshot={"name": "rsi"},
                change_description="Initial version",
                created_by=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/specs/{spec_id}/versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "strategy_version"

    def test_list_versions_spec_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/specs/{uuid.uuid4()}/versions")
        assert resp.status_code == 404


class TestGetVersion:
    def test_get_version(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        version_id = uuid.uuid4()

        # fetchrow called twice: spec check, then version fetch
        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),
            FakeRecord(
                id=version_id,
                strategy_id=spec_id,
                version_number=1,
                config_snapshot={"name": "rsi"},
                change_description="Initial version",
                created_by=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get(f"/specs/{spec_id}/versions/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version_number"] == 1

    def test_get_version_not_found(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),  # spec exists
            None,  # version not found
        ]

        resp = tc.get(f"/specs/{spec_id}/versions/999")
        assert resp.status_code == 404


class TestRestoreVersion:
    def test_restore_version(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()
        version_id = uuid.uuid4()
        new_version_id = uuid.uuid4()

        snapshot = {
            "name": "rsi",
            "indicators": {"rsi": {"period": 14}},
            "entry_conditions": {},
            "exit_conditions": {},
            "parameters": {},
            "description": "RSI strategy",
        }

        # fetchrow calls: spec check, version fetch, spec for snapshot,
        # then create_version_snapshot internals (spec fetch + insert)
        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),  # spec exists
            FakeRecord(config_snapshot=snapshot),  # version to restore
            # create_version_snapshot: _get_spec
            FakeRecord(
                id=spec_id,
                name="rsi",
                indicators={"rsi": {"period": 14}},
                entry_conditions={},
                exit_conditions={},
                parameters={},
                description="RSI strategy",
                source="USER_CREATED",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            # create_version_snapshot: INSERT
            FakeRecord(
                id=new_version_id,
                strategy_id=spec_id,
                version_number=2,
                config_snapshot=snapshot,
                change_description="Restored to version 1",
                created_by=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchval.return_value = 1  # max version_number
        conn.execute.return_value = None

        resp = tc.post(f"/specs/{spec_id}/versions/1/restore")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["version_number"] == 2

    def test_restore_version_not_found(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),  # spec exists
            None,  # version not found
        ]

        resp = tc.post(f"/specs/{spec_id}/versions/999/restore")
        assert resp.status_code == 404


class TestDiffVersions:
    def test_diff_versions(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),  # spec exists
            FakeRecord(
                config_snapshot={"name": "rsi", "indicators": {"rsi": {"period": 14}}}
            ),
            FakeRecord(
                config_snapshot={"name": "rsi", "indicators": {"rsi": {"period": 21}}}
            ),
        ]

        resp = tc.get(f"/specs/{spec_id}/versions/diff?v1=1&v2=2")
        assert resp.status_code == 200
        body = resp.json()
        changes = body["data"]["attributes"]["changes"]
        assert len(changes) == 1
        assert changes[0]["field"] == "indicators.rsi.period"
        assert changes[0]["old_value"] == 14
        assert changes[0]["new_value"] == 21

    def test_diff_version_not_found(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=spec_id),
            None,  # v1 not found
            FakeRecord(config_snapshot={"name": "rsi"}),
        ]

        resp = tc.get(f"/specs/{spec_id}/versions/diff?v1=1&v2=2")
        assert resp.status_code == 404

    def test_diff_missing_params(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        resp = tc.get(f"/specs/{spec_id}/versions/diff")
        assert resp.status_code == 422


class TestAutoVersioningOnCreate:
    def test_create_spec_creates_version(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        # create_spec: INSERT spec, then create_version_snapshot (_get_spec + max + INSERT version)
        conn.fetchrow.side_effect = [
            FakeRecord(
                id=spec_id,
                name="new_spec",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            # create_version_snapshot: _get_spec
            FakeRecord(
                id=spec_id,
                name="new_spec",
                indicators={"rsi": {"period": 14}},
                entry_conditions={"rsi_below": 30},
                exit_conditions={"rsi_above": 70},
                parameters={"period": {"min": 5, "max": 30}},
                description="Test spec",
                source="LLM_GENERATED",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            # create_version_snapshot: INSERT version
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=spec_id,
                version_number=1,
                config_snapshot={},
                change_description="Initial version",
                created_by=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchval.return_value = 0  # no existing versions

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


class TestAutoVersioningOnUpdate:
    def test_update_spec_creates_version(self, client):
        tc, conn = client
        spec_id = uuid.uuid4()

        # update_spec: UPDATE returns row, then create_version_snapshot
        conn.fetchrow.side_effect = [
            # UPDATE RETURNING
            FakeRecord(
                id=spec_id,
                name="rsi",
                indicators={"rsi": {"period": 21}},
                entry_conditions={},
                exit_conditions={},
                parameters={},
                description="RSI updated",
                source="USER_CREATED",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            # create_version_snapshot: _get_spec
            FakeRecord(
                id=spec_id,
                name="rsi",
                indicators={"rsi": {"period": 21}},
                entry_conditions={},
                exit_conditions={},
                parameters={},
                description="RSI updated",
                source="USER_CREATED",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            # create_version_snapshot: INSERT version
            FakeRecord(
                id=uuid.uuid4(),
                strategy_id=spec_id,
                version_number=2,
                config_snapshot={},
                change_description="Config updated",
                created_by=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchval.return_value = 1  # existing version

        resp = tc.put(
            f"/specs/{spec_id}",
            json={"description": "RSI updated"},
        )
        assert resp.status_code == 200
