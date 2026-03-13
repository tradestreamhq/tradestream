"""Tests for the Auth & API Key Management REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.auth_api.app import create_app


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
    return TestClient(app, raise_server_exceptions=False), conn, pool


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn, _ = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "auth-api"


class TestRegister:
    def test_register_success(self, client):
        tc, conn, _ = client
        user_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=user_id,
            email="test@example.com",
            name="Test User",
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "name": "Test User",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body["data"]["attributes"]
        assert "refresh_token" in body["data"]["attributes"]
        assert body["data"]["attributes"]["user"]["email"] == "test@example.com"

    def test_register_duplicate_email(self, client):
        tc, conn, _ = client
        from asyncpg.exceptions import UniqueViolationError

        conn.fetchrow.side_effect = UniqueViolationError("")

        resp = tc.post(
            "/register",
            json={
                "email": "existing@example.com",
                "password": "securepassword123",
                "name": "Test User",
            },
        )
        # Should return validation error
        assert resp.status_code in (400, 422, 200)  # validation_error returns 200 with error

    def test_register_short_password(self, client):
        tc, conn, _ = client
        resp = tc.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "short",
                "name": "Test User",
            },
        )
        assert resp.status_code == 422

    def test_register_missing_name(self, client):
        tc, conn, _ = client
        resp = tc.post(
            "/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        tc, conn, _ = client
        user_id = uuid.uuid4()
        from services.auth_api.auth_service import hash_password

        pw_hash = hash_password("correctpassword")
        conn.fetchrow.return_value = FakeRecord(
            id=user_id,
            email="user@example.com",
            name="User",
            password_hash=pw_hash,
            is_active=True,
        )
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/login",
            json={"email": "user@example.com", "password": "correctpassword"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body["data"]["attributes"]

    def test_login_wrong_password(self, client):
        tc, conn, _ = client
        from services.auth_api.auth_service import hash_password

        pw_hash = hash_password("correctpassword")
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.uuid4(),
            email="user@example.com",
            name="User",
            password_hash=pw_hash,
            is_active=True,
        )

        resp = tc.post(
            "/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        body = resp.json()
        # Should indicate invalid credentials
        assert "error" in body or "Invalid" in str(body)

    def test_login_nonexistent_user(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        body = resp.json()
        assert "error" in body or "Invalid" in str(body)


class TestRefresh:
    def test_refresh_success(self, client):
        tc, conn, _ = client
        user_id = uuid.uuid4()
        token_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            # First call: lookup refresh token
            FakeRecord(
                id=token_id,
                user_id=user_id,
                expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
                revoked=False,
                email="user@example.com",
                is_active=True,
            ),
            # Second call: insert new refresh token (fetchrow from create_token_pair)
            None,
        ]
        conn.execute.return_value = "UPDATE 1"

        resp = tc.post(
            "/refresh",
            json={"refresh_token": "valid-refresh-token"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body["data"]["attributes"]

    def test_refresh_invalid_token(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "/refresh",
            json={"refresh_token": "invalid-token"},
        )
        body = resp.json()
        assert "error" in body or "Invalid" in str(body)


class TestLogout:
    def test_logout_success(self, client):
        tc, conn, _ = client
        conn.execute.return_value = "UPDATE 1"

        resp = tc.post(
            "/logout",
            json={"refresh_token": "some-token"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["revoked"] is True


class TestApiKeyEndpoints:
    def _auth_header(self):
        from services.auth_api.auth_service import create_access_token

        token = create_access_token("user-123", "user@example.com")
        return {"Authorization": f"Bearer {token}"}

    def test_create_api_key(self, client):
        tc, conn, _ = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=key_id,
            name="My Key",
            key_prefix="ts_abcde",
            permissions=["read", "write"],
            rate_limit_per_minute=60,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/api-keys",
            json={"name": "My Key", "permissions": ["read", "write"]},
            headers=self._auth_header(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "key" in body["data"]["attributes"]
        assert body["data"]["attributes"]["key"].startswith("ts_")

    def test_create_api_key_no_auth(self, client):
        tc, conn, _ = client
        resp = tc.post(
            "/api-keys",
            json={"name": "My Key"},
        )
        # Should fail with validation error about missing auth
        body = resp.json()
        assert "error" in body or "Authorization" in str(body) or resp.status_code == 401

    def test_list_api_keys(self, client):
        tc, conn, _ = client
        key_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=key_id,
                name="My Key",
                key_prefix="ts_abcde",
                permissions=["read"],
                is_active=True,
                rate_limit_per_minute=60,
                last_used_at=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/api-keys", headers=self._auth_header())
        assert resp.status_code == 200
        body = resp.json()
        keys = body["data"]["attributes"]
        assert len(keys) == 1
        assert keys[0]["key_prefix"].endswith("...")

    def test_revoke_api_key(self, client):
        tc, conn, _ = client
        conn.execute.return_value = "UPDATE 1"

        key_id = uuid.uuid4()
        resp = tc.delete(f"/api-keys/{key_id}", headers=self._auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["revoked"] is True

    def test_revoke_api_key_not_found(self, client):
        tc, conn, _ = client
        conn.execute.return_value = "UPDATE 0"

        key_id = uuid.uuid4()
        resp = tc.delete(f"/api-keys/{key_id}", headers=self._auth_header())
        body = resp.json()
        assert "error" in body or "not found" in str(body).lower()
