"""Tests for the API Key Management REST API."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api_key_api.app import (
    ApiKeyAuthMiddleware,
    RateLimiter,
    create_app,
    generate_api_key,
    verify_api_key,
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


# --- Key generation tests ---


class TestKeyGeneration:
    def test_generate_live_key(self):
        full_key, prefix, key_hash = generate_api_key("live")
        assert full_key.startswith("ts_live_")
        assert prefix == "ts_live_"
        assert len(full_key) > len("ts_live_")
        assert "$" in key_hash

    def test_generate_test_key(self):
        full_key, prefix, key_hash = generate_api_key("test")
        assert full_key.startswith("ts_test_")
        assert prefix == "ts_test_"

    def test_verify_key_correct(self):
        full_key, _, key_hash = generate_api_key("live")
        assert verify_api_key(full_key, key_hash) is True

    def test_verify_key_incorrect(self):
        _, _, key_hash = generate_api_key("live")
        assert verify_api_key("ts_live_wrong_key", key_hash) is False

    def test_verify_key_malformed_hash(self):
        assert verify_api_key("ts_live_key", "no_dollar_sign") is False

    def test_keys_are_unique(self):
        key1, _, _ = generate_api_key("live")
        key2, _, _ = generate_api_key("live")
        assert key1 != key2


# --- Rate limiter tests ---


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter()
        for _ in range(5):
            assert limiter.is_allowed("key1", 10) is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter()
        for _ in range(5):
            limiter.is_allowed("key1", 5)
        assert limiter.is_allowed("key1", 5) is False

    def test_separate_keys(self):
        limiter = RateLimiter()
        for _ in range(5):
            limiter.is_allowed("key1", 5)
        # key2 should still be allowed
        assert limiter.is_allowed("key2", 5) is True


# --- Health endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "api-key-api"


# --- Create API key tests ---


class TestCreateApiKey:
    def test_create_live_key(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=key_id,
            name="my-key",
            key_prefix="ts_live_",
            permissions=["read", "write"],
            expires_at=None,
            rate_limit_per_minute=60,
            created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "",
            json={
                "name": "my-key",
                "permissions": ["read", "write"],
                "environment": "live",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(key_id)
        attrs = body["data"]["attributes"]
        assert attrs["name"] == "my-key"
        assert attrs["key"].startswith("ts_live_")
        assert attrs["key_prefix"] == "ts_live_"
        assert attrs["permissions"] == ["read", "write"]

    def test_create_test_key(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=key_id,
            name="test-key",
            key_prefix="ts_test_",
            permissions=["read"],
            expires_at=None,
            rate_limit_per_minute=100,
            created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "",
            json={
                "name": "test-key",
                "permissions": ["read"],
                "environment": "test",
                "rate_limit_per_minute": 100,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["key"].startswith("ts_test_")

    def test_create_key_with_expiry(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        expiry = datetime(2026, 12, 31, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=key_id,
            name="expiring-key",
            key_prefix="ts_live_",
            permissions=["read"],
            expires_at=expiry,
            rate_limit_per_minute=60,
            created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "",
            json={
                "name": "expiring-key",
                "permissions": ["read"],
                "expires_at": "2026-12-31T00:00:00+00:00",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["expires_at"] is not None

    def test_create_key_invalid_expiry(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "",
            json={
                "name": "bad-expiry",
                "permissions": ["read"],
                "expires_at": "not-a-date",
            },
        )
        assert resp.status_code == 422

    def test_create_key_missing_name(self, client):
        tc, conn = client
        resp = tc.post("", json={"permissions": ["read"]})
        assert resp.status_code == 422

    def test_create_key_missing_permissions(self, client):
        tc, conn = client
        resp = tc.post("", json={"name": "no-perms"})
        assert resp.status_code == 422

    def test_create_key_empty_permissions(self, client):
        tc, conn = client
        resp = tc.post(
            "", json={"name": "empty-perms", "permissions": []}
        )
        assert resp.status_code == 422

    def test_create_key_invalid_environment(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "name": "bad-env",
                "permissions": ["read"],
                "environment": "staging",
            },
        )
        assert resp.status_code == 422


# --- List API keys tests ---


class TestListApiKeys:
    def test_list_keys(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=key_id,
                name="my-key",
                key_prefix="ts_live_",
                permissions=["read"],
                expires_at=None,
                is_revoked=False,
                request_count=42,
                last_used_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
                rate_limit_per_minute=60,
                created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["name"] == "my-key"
        assert attrs["key_prefix"] == "ts_live_"
        assert attrs["request_count"] == 42
        # Full key should never be present
        assert "key" not in attrs
        assert "key_hash" not in attrs

    def test_list_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert len(body["data"]) == 0

    def test_list_with_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("?limit=10&offset=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 5


# --- Revoke API key tests ---


class TestRevokeApiKey:
    def test_revoke_key(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=key_id)

        resp = tc.delete(f"/{key_id}")
        assert resp.status_code == 204

    def test_revoke_nonexistent_key(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_revoke_already_revoked_key(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None  # query finds no unrevoked key

        resp = tc.delete(f"/{uuid.uuid4()}")
        assert resp.status_code == 404


# --- Middleware tests ---


class TestApiKeyAuthMiddleware:
    def _make_middleware_app(self, conn):
        """Create a minimal app with API key auth middleware for testing."""
        from fastapi import FastAPI

        pool, _ = _make_pool()
        # Override the connection returned by pool
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx

        app = FastAPI()
        app.add_middleware(ApiKeyAuthMiddleware, db_pool=pool)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {
                "key_id": request.state.api_key_id,
                "permissions": request.state.api_key_permissions,
            }

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return TestClient(app, raise_server_exceptions=False)

    def test_health_bypasses_auth(self):
        conn = AsyncMock()
        tc = self._make_middleware_app(conn)
        resp = tc.get("/health")
        assert resp.status_code == 200

    def test_missing_key_returns_401(self):
        conn = AsyncMock()
        tc = self._make_middleware_app(conn)
        resp = tc.get("/test")
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["error"]["message"]

    def test_invalid_prefix_returns_401(self):
        conn = AsyncMock()
        tc = self._make_middleware_app(conn)
        resp = tc.get("/test", headers={"X-API-Key": "invalid_prefix_key"})
        assert resp.status_code == 401
        assert "Invalid API key format" in resp.json()["error"]["message"]

    def test_valid_key_passes(self):
        conn = AsyncMock()
        full_key, prefix, key_hash = generate_api_key("live")
        key_id = uuid.uuid4()

        conn.fetch.return_value = [
            FakeRecord(
                id=key_id,
                key_hash=key_hash,
                permissions=["read", "write"],
                expires_at=None,
                is_revoked=False,
                rate_limit_per_minute=60,
            )
        ]

        tc = self._make_middleware_app(conn)
        resp = tc.get("/test", headers={"X-API-Key": full_key})
        assert resp.status_code == 200
        body = resp.json()
        assert body["key_id"] == str(key_id)
        assert body["permissions"] == ["read", "write"]

    def test_wrong_key_returns_401(self):
        conn = AsyncMock()
        _, prefix, key_hash = generate_api_key("live")

        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                key_hash=key_hash,
                permissions=["read"],
                expires_at=None,
                is_revoked=False,
                rate_limit_per_minute=60,
            )
        ]

        tc = self._make_middleware_app(conn)
        resp = tc.get(
            "/test", headers={"X-API-Key": "ts_live_wrong_key_value_here"}
        )
        assert resp.status_code == 401

    def test_expired_key_returns_401(self):
        conn = AsyncMock()
        full_key, prefix, key_hash = generate_api_key("live")

        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                key_hash=key_hash,
                permissions=["read"],
                expires_at=datetime(2020, 1, 1),  # expired
                is_revoked=False,
                rate_limit_per_minute=60,
            )
        ]

        tc = self._make_middleware_app(conn)
        resp = tc.get("/test", headers={"X-API-Key": full_key})
        assert resp.status_code == 401
        assert "expired" in resp.json()["error"]["message"]

    def test_rate_limited_returns_429(self):
        conn = AsyncMock()
        full_key, prefix, key_hash = generate_api_key("live")
        key_id = uuid.uuid4()

        conn.fetch.return_value = [
            FakeRecord(
                id=key_id,
                key_hash=key_hash,
                permissions=["read"],
                expires_at=None,
                is_revoked=False,
                rate_limit_per_minute=2,  # very low limit
            )
        ]

        tc = self._make_middleware_app(conn)
        # First two requests should pass
        for _ in range(2):
            resp = tc.get("/test", headers={"X-API-Key": full_key})
            assert resp.status_code == 200

        # Third should be rate limited
        resp = tc.get("/test", headers={"X-API-Key": full_key})
        assert resp.status_code == 429
        assert "Rate limit" in resp.json()["error"]["message"]

    def test_no_matching_keys_returns_401(self):
        conn = AsyncMock()
        conn.fetch.return_value = []  # no keys in DB

        tc = self._make_middleware_app(conn)
        resp = tc.get(
            "/test", headers={"X-API-Key": "ts_live_some_random_key_value"}
        )
        assert resp.status_code == 401
