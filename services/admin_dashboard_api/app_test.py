"""Tests for the Admin Dashboard REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, mock_open, patch

import pytest
from fastapi.testclient import TestClient

from services.admin_dashboard_api.app import create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


ADMIN_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())

ADMIN_ROW = FakeRecord(
    id=uuid.UUID(ADMIN_ID),
    username="admin",
    role="admin",
    is_active=True,
)

NON_ADMIN_ROW = FakeRecord(
    id=uuid.UUID(USER_ID),
    username="trader1",
    role="trader",
    is_active=True,
)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _admin_headers():
    return {"X-Admin-User-Id": ADMIN_ID}


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# ======================================================================
# Health
# ======================================================================


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# ======================================================================
# Auth / Admin role checks
# ======================================================================


class TestAdminAuth:
    def test_missing_admin_header(self, client):
        tc, conn = client
        resp = tc.get("/users")
        assert resp.status_code == 422

    def test_non_admin_user(self, client):
        tc, conn = client
        conn.fetchrow.return_value = NON_ADMIN_ROW
        resp = tc.get("/users", headers={"X-Admin-User-Id": USER_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("error", {}).get("code") == "FORBIDDEN"

    def test_unknown_admin_user(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get("/users", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("error", {}).get("code") == "FORBIDDEN"


# ======================================================================
# List users
# ======================================================================


class TestListUsers:
    def test_list_users(self, client):
        tc, conn = client
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = ADMIN_ROW
        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.UUID(USER_ID),
                username="trader1",
                email="trader1@example.com",
                role="trader",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/users", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1

    def test_list_users_with_pagination(self, client):
        tc, conn = client
        conn.fetchrow.return_value = ADMIN_ROW
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/users?limit=10&offset=5", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 5


# ======================================================================
# Update user role
# ======================================================================


class TestUpdateUserRole:
    def test_update_role_success(self, client):
        tc, conn = client
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.side_effect = [
            ADMIN_ROW,
            FakeRecord(
                id=uuid.UUID(USER_ID),
                username="trader1",
                email="trader1@example.com",
                role="admin",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ]

        resp = tc.put(
            f"/users/{USER_ID}/role",
            json={"role": "admin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["role"] == "admin"

    def test_update_role_invalid(self, client):
        tc, conn = client
        conn.fetchrow.return_value = ADMIN_ROW

        resp = tc.put(
            f"/users/{USER_ID}/role",
            json={"role": "superadmin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("error", {}).get("code") == "VALIDATION_ERROR"

    def test_update_role_user_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [ADMIN_ROW, None]

        resp = tc.put(
            f"/users/{USER_ID}/role",
            json={"role": "viewer"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("error", {}).get("code") == "NOT_FOUND"


# ======================================================================
# Update user status
# ======================================================================


class TestUpdateUserStatus:
    def test_deactivate_user(self, client):
        tc, conn = client
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.side_effect = [
            ADMIN_ROW,
            FakeRecord(
                id=uuid.UUID(USER_ID),
                username="trader1",
                email="trader1@example.com",
                role="trader",
                is_active=False,
                created_at=now,
                updated_at=now,
            ),
        ]

        resp = tc.put(
            f"/users/{USER_ID}/status",
            json={"is_active": False},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["is_active"] is False

    def test_status_user_not_found(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [ADMIN_ROW, None]

        resp = tc.put(
            f"/users/{USER_ID}/status",
            json={"is_active": True},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("error", {}).get("code") == "NOT_FOUND"


# ======================================================================
# System health
# ======================================================================

FAKE_MEMINFO = """\
MemTotal:       16384000 kB
MemFree:         4096000 kB
MemAvailable:    8192000 kB
Buffers:          512000 kB
Cached:          2048000 kB
"""


class TestSystemHealth:
    @patch(
        "builtins.open", mock_open(read_data=FAKE_MEMINFO)
    )
    def test_system_health(self, client):
        tc, conn = client
        conn.fetchrow.return_value = ADMIN_ROW
        conn.fetchval.side_effect = [10, 3, 5]

        resp = tc.get("/system", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["active_strategies"] == 10
        assert attrs["open_positions"] == 3
        assert attrs["db_connections"] == 5
        assert "memory" in attrs
        assert attrs["memory"]["total_mb"] > 0


# ======================================================================
# Audit log
# ======================================================================


class TestAuditLog:
    def test_get_audit_log(self, client):
        tc, conn = client
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        audit_id = uuid.uuid4()

        conn.fetchrow.return_value = ADMIN_ROW
        conn.fetch.return_value = [
            FakeRecord(
                id=audit_id,
                user_id=uuid.UUID(ADMIN_ID),
                username="admin",
                action="update_role",
                resource_type="user",
                resource_id=USER_ID,
                changes='{"role": "admin"}',
                ip_address="127.0.0.1",
                created_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/audit-log", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["action"] == "update_role"


# ======================================================================
# Platform metrics
# ======================================================================


class TestMetrics:
    def test_get_metrics(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            ADMIN_ROW,
            FakeRecord(total_pnl=5000.0, gross_profit=8000.0, gross_loss=-3000.0),
        ]
        conn.fetchval.side_effect = [100, 5, 95, 10, 20]

        resp = tc.get("/metrics", headers=_admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_trades"] == 100
        assert attrs["active_users"] == 10
        assert attrs["revenue"]["total_pnl"] == 5000.0
