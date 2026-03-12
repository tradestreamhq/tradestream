"""Tests for the Exchange Account Manager REST API."""

import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.exchange_account_manager.app import create_app


class FakeRecord(dict):
    """Minimal asyncpg-Record stand-in that supports both key and attr access."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


_NOW = datetime(2026, 3, 12, tzinfo=timezone.utc)
_ACCOUNT_ID = str(uuid.uuid4())


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _account_row(**overrides):
    defaults = dict(
        id=_ACCOUNT_ID,
        exchange="binance",
        label="My Binance",
        permissions='["read"]',
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return FakeRecord(**defaults)


@pytest.fixture(autouse=True)
def _set_encryption_key():
    with patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": "test-secret-key"}):
        yield


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# ---- Health ----


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# ---- CRUD ----


class TestCreateAccount:
    def test_create(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _account_row()

        resp = tc.post(
            "/accounts",
            json={
                "exchange": "binance",
                "label": "My Binance",
                "api_key": "ak123",
                "api_secret": "as456",
                "permissions": ["read"],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "exchange_account"
        assert body["data"]["attributes"]["exchange"] == "binance"

    def test_create_missing_key(self, client):
        tc, _ = client
        resp = tc.post(
            "/accounts",
            json={"exchange": "binance", "label": "x", "api_key": "", "api_secret": "s"},
        )
        assert resp.status_code == 422


class TestListAccounts:
    def test_list(self, client):
        tc, conn = client
        conn.fetch.return_value = [_account_row(), _account_row(label="Second")]
        resp = tc.get("/accounts")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2


class TestGetAccount:
    def test_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _account_row()
        resp = tc.get(f"/accounts/{_ACCOUNT_ID}")
        assert resp.status_code == 200

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/accounts/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateAccount:
    def test_update_label(self, client):
        tc, conn = client
        # First call: _fetch_account, second call: UPDATE RETURNING
        conn.fetchrow.side_effect = [
            _account_row(),
            _account_row(label="Renamed"),
        ]
        resp = tc.patch(
            f"/accounts/{_ACCOUNT_ID}",
            json={"label": "Renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["label"] == "Renamed"

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.patch(f"/accounts/{uuid.uuid4()}", json={"label": "x"})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _account_row()
        resp = tc.patch(f"/accounts/{_ACCOUNT_ID}", json={})
        assert resp.status_code == 422


class TestDeleteAccount:
    def test_delete(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(id=_ACCOUNT_ID)
        resp = tc.delete(f"/accounts/{_ACCOUNT_ID}")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["deleted"] is True

    def test_delete_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.delete(f"/accounts/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---- Balances ----


class TestBalances:
    @patch("services.exchange_account_manager.exchange_client.fetch_balances")
    def test_get_balances(self, mock_fetch, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=_ACCOUNT_ID,
            exchange="binance",
            label="My Binance",
            encrypted_api_key="enc_key",
            encrypted_api_secret="enc_secret",
        )
        mock_fetch.return_value = {"BTC": 1.0, "USDT": 5000.0}

        with patch(
            "services.exchange_account_manager.app.credential_store.decrypt",
            side_effect=lambda x: "decrypted",
        ):
            resp = tc.get(f"/accounts/{_ACCOUNT_ID}/balances")

        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "BTC" in attrs["balances"]
        assert attrs["total_usd"] > 0

    def test_get_balances_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get(f"/accounts/{uuid.uuid4()}/balances")
        assert resp.status_code == 404


# ---- Unified portfolio ----


class TestUnifiedPortfolio:
    @patch("services.exchange_account_manager.exchange_client.fetch_balances")
    def test_portfolio(self, mock_fetch, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=_ACCOUNT_ID,
                exchange="binance",
                label="Binance",
                encrypted_api_key="ek",
                encrypted_api_secret="es",
            ),
        ]
        mock_fetch.return_value = {"BTC": 0.5, "ETH": 2.0}

        with patch(
            "services.exchange_account_manager.app.credential_store.decrypt",
            side_effect=lambda x: "decrypted",
        ):
            resp = tc.get("/portfolio")

        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert len(attrs["accounts"]) == 1
        assert attrs["total_usd"] > 0
        assert "BTC" in attrs["asset_totals"]
