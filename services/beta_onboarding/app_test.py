"""Tests for Beta Onboarding API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.beta_onboarding.app import create_app


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


class TestRedeemInvite:
    def test_invalid_code_returns_404(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/redeem", json={
            "code": "INVALID-CODE",
            "email": "test@example.com",
        })
        assert resp.status_code == 404

    def test_valid_code_creates_user(self):
        pool, conn = _make_pool()
        invite_id = str(uuid.uuid4())
        conn.fetchrow.side_effect = [
            # First: find invite code
            FakeRecord(
                id=invite_id, code="TRADESTREAM-BETA-001",
                max_uses=50, current_uses=0, tier="pro",
                expires_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                is_active=True,
            ),
            # Second: check existing beta user
            None,
        ]
        conn.execute.return_value = None

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/redeem", json={
            "code": "TRADESTREAM-BETA-001",
            "email": "beta@example.com",
        })
        assert resp.status_code == 201
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["tier"] == "pro"
        assert attrs["onboarding_step"] == "REGISTERED"

    def test_exhausted_code_returns_410(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(
            id="inv-1", code="USED-UP", max_uses=1, current_uses=1,
            tier="pro", expires_at=None, is_active=True,
        )

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/redeem", json={
            "code": "USED-UP",
            "email": "test@example.com",
        })
        assert resp.status_code == 410

    def test_inactive_code_returns_410(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(
            id="inv-2", code="DISABLED", max_uses=50, current_uses=0,
            tier="pro", expires_at=None, is_active=False,
        )

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/redeem", json={
            "code": "DISABLED",
            "email": "test@example.com",
        })
        assert resp.status_code == 410


class TestConnectTelegram:
    def test_connect_updates_step(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(
            id="beta-1", customer_id="cust-1",
            onboarding_step="REGISTERED",
        )
        conn.execute.return_value = None

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/users/beta-1/connect-telegram", json={
            "telegram_chat_id": "123456789",
        })
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["onboarding_step"] == "TELEGRAM_CONNECTED"

    def test_unknown_user_returns_404(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/users/nonexistent/connect-telegram", json={
            "telegram_chat_id": "123456789",
        })
        assert resp.status_code == 404


class TestSelectStrategies:
    def test_valid_strategies_accepted(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(
            id="beta-1", telegram_chat_id="123456789", customer_id="cust-1",
        )
        conn.fetch.return_value = [
            FakeRecord(name="MACD_CROSSOVER"),
            FakeRecord(name="RSI_EMA_CROSSOVER"),
        ]
        conn.execute.return_value = None

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/users/beta-1/select-strategies", json={
            "strategies": ["MACD_CROSSOVER", "RSI_EMA_CROSSOVER"],
            "pairs": ["BTC/USD", "ETH/USD"],
        })
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["onboarding_step"] == "STRATEGY_SELECTED"

    def test_invalid_strategy_returns_422(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(
            id="beta-1", telegram_chat_id="123", customer_id="cust-1",
        )
        conn.fetch.return_value = [FakeRecord(name="MACD_CROSSOVER")]

        app = create_app(pool)
        client = TestClient(app)

        resp = client.post("/users/beta-1/select-strategies", json={
            "strategies": ["MACD_CROSSOVER", "NONEXISTENT_STRATEGY"],
            "pairs": ["BTC/USD"],
        })
        assert resp.status_code == 422


class TestListInviteCodes:
    def test_list_returns_codes(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            FakeRecord(
                id="inv-1", code="BETA-001", created_by="system",
                max_uses=50, current_uses=10, tier="pro",
                expires_at=None, is_active=True, created_at=None,
            ),
        ]

        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/invite-codes")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["attributes"]["remaining"] == 40
