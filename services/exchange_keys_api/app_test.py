"""Tests for the Exchange Keys REST API."""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.exchange_keys_api.app import create_app


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


def _sample_row(key_id=None, exchange="binance"):
    from services.exchange_keys_api.encryption import encrypt

    kid = key_id or uuid.uuid4()
    return FakeRecord(
        id=kid,
        exchange_name=exchange,
        api_key_encrypted=encrypt("test-api-key-12345"),
        api_secret_encrypted=encrypt("test-api-secret-67890"),
        label="My Binance Key",
        permissions=["read", "trade"],
        is_active=True,
        last_used_at=None,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )


@pytest.fixture(autouse=True)
def _set_encryption_secret():
    with patch.dict(
        os.environ, {"EXCHANGE_KEY_ENCRYPTION_SECRET": "test-secret-key-12345"}
    ):
        yield


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestCreateKey:
    def test_create_success(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = _sample_row(key_id)

        resp = tc.post(
            "/keys",
            json={
                "exchange_name": "binance",
                "api_key": "test-api-key-12345",
                "api_secret": "test-api-secret-67890",
                "label": "My Binance Key",
                "permissions": ["read", "trade"],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["exchange_name"] == "binance"
        # Secrets must be masked
        assert "test-api-key" not in attrs["api_key"]
        assert "****" in attrs["api_key"]
        assert attrs["api_secret"] == "****"

    def test_create_invalid_permissions(self, client):
        tc, conn = client
        resp = tc.post(
            "/keys",
            json={
                "exchange_name": "binance",
                "api_key": "key",
                "api_secret": "secret",
                "permissions": ["read", "admin"],
            },
        )
        assert resp.status_code == 422
        assert "admin" in resp.json()["error"]["message"]


class TestListKeys:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetch.return_value = [_sample_row(), _sample_row()]

        resp = tc.get("/keys")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_list_by_exchange(self, client):
        tc, conn = client
        conn.fetch.return_value = [_sample_row()]

        resp = tc.get("/keys?exchange_name=binance")
        assert resp.status_code == 200


class TestGetKey:
    def test_get_found(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = _sample_row(key_id)

        resp = tc.get(f"/keys/{key_id}")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["api_secret"] == "****"

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/keys/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_invalid_id(self, client):
        tc, conn = client
        resp = tc.get("/keys/not-a-uuid")
        assert resp.status_code == 422


class TestUpdateKey:
    def test_update_label(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        updated = _sample_row(key_id)
        updated["label"] = "Updated Label"
        conn.fetchrow.return_value = updated

        resp = tc.patch(f"/keys/{key_id}", json={"label": "Updated Label"})
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["label"] == "Updated Label"

    def test_update_no_fields(self, client):
        tc, conn = client
        resp = tc.patch(f"/keys/{uuid.uuid4()}", json={})
        assert resp.status_code == 422

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.patch(f"/keys/{uuid.uuid4()}", json={"label": "x"})
        assert resp.status_code == 404


class TestDeleteKey:
    def test_delete_success(self, client):
        tc, conn = client
        conn.execute.return_value = "DELETE 1"

        resp = tc.delete(f"/keys/{uuid.uuid4()}")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["deleted"] is True

    def test_delete_not_found(self, client):
        tc, conn = client
        conn.execute.return_value = "DELETE 0"

        resp = tc.delete(f"/keys/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTestKey:
    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(f"/keys/{uuid.uuid4()}/test")
        assert resp.status_code == 404

    def test_valid_key(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = _sample_row(key_id)

        with patch("services.exchange_keys_api.app.ccxt") as mock_ccxt:
            mock_exchange = mock_ccxt.binance.return_value
            mock_exchange.fetch_balance.return_value = {"total": {}}

            resp = tc.post(f"/keys/{key_id}/test")
            assert resp.status_code == 200
            attrs = resp.json()["data"]["attributes"]
            assert attrs["valid"] is True

    def test_auth_failure(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = _sample_row(key_id)

        with patch("services.exchange_keys_api.app.ccxt") as mock_ccxt:
            import ccxt

            mock_exchange = mock_ccxt.binance.return_value
            mock_exchange.fetch_balance.side_effect = ccxt.AuthenticationError("bad key")

            resp = tc.post(f"/keys/{key_id}/test")
            assert resp.status_code == 200
            attrs = resp.json()["data"]["attributes"]
            assert attrs["valid"] is False


class TestRotateKey:
    def test_rotate_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/keys/{uuid.uuid4()}/rotate",
            json={"api_key": "new-key", "api_secret": "new-secret"},
        )
        assert resp.status_code == 404

    def test_rotate_success(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        row = _sample_row(key_id)
        # First fetchrow returns existing, second returns updated
        conn.fetchrow.side_effect = [row, row]

        with patch("services.exchange_keys_api.app.ccxt") as mock_ccxt:
            mock_exchange = mock_ccxt.binance.return_value
            mock_exchange.fetch_balance.return_value = {"total": {}}

            resp = tc.post(
                f"/keys/{key_id}/rotate",
                json={"api_key": "new-key", "api_secret": "new-secret"},
            )
            assert resp.status_code == 200
            attrs = resp.json()["data"]["attributes"]
            assert attrs["api_secret"] == "****"

    def test_rotate_verification_fails(self, client):
        tc, conn = client
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = _sample_row(key_id)

        with patch("services.exchange_keys_api.app.ccxt") as mock_ccxt:
            mock_exchange = mock_ccxt.binance.return_value
            mock_exchange.fetch_balance.side_effect = Exception("Connection refused")

            resp = tc.post(
                f"/keys/{key_id}/rotate",
                json={"api_key": "bad-key", "api_secret": "bad-secret"},
            )
            assert resp.status_code == 422
            assert "verification" in resp.json()["error"]["message"].lower()
