"""Tests for the Billing REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.billing.app import create_app


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


class TestListPlans:
    def test_returns_all_plans(self, client):
        tc, _, _ = client
        resp = tc.get("/plans")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        tiers = {item["attributes"]["tier"] for item in body["data"]}
        assert tiers == {"free", "pro", "enterprise"}


class TestCheckout:
    @patch("services.billing.app.stripe")
    def test_checkout_success(self, mock_stripe, client):
        tc, _, _ = client
        mock_stripe.api_key = "sk-test"
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session/test"
        mock_session.id = "cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        with patch.dict("os.environ", {
            "STRIPE_SECRET_KEY": "sk-test",
            "STRIPE_PRO_PRICE_ID": "price_pro_test",
        }):
            resp = tc.post("/checkout", json={
                "tier": "pro",
                "email": "user@example.com",
                "success_url": "https://tradestream.io/success",
                "cancel_url": "https://tradestream.io/cancel",
            })

        assert resp.status_code == 201
        body = resp.json()
        assert "checkout_url" in body["data"]["attributes"]

    def test_checkout_invalid_tier(self, client):
        tc, _, _ = client
        resp = tc.post("/checkout", json={
            "tier": "free",
            "email": "user@example.com",
            "success_url": "https://tradestream.io/success",
            "cancel_url": "https://tradestream.io/cancel",
        })
        assert resp.status_code == 422


class TestSubscription:
    def test_get_subscription_by_email(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = FakeRecord(
            id=uuid.uuid4(),
            email="user@example.com",
            telegram_chat_id="12345",
            tier="pro",
            status="active",
            current_period_end=datetime(2026, 4, 19, tzinfo=timezone.utc),
            cancel_at_period_end=False,
        )

        resp = tc.get("/subscription?email=user@example.com")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["tier"] == "pro"
        assert attrs["plan"]["price_monthly"] == 29.0

    def test_get_subscription_not_found(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = None

        resp = tc.get("/subscription?email=nobody@example.com")
        assert resp.status_code == 404

    def test_get_subscription_no_params(self, client):
        tc, _, _ = client
        resp = tc.get("/subscription")
        assert resp.status_code == 422


class TestWebhook:
    def test_webhook_subscription_created(self, client):
        tc, conn, _ = client
        conn.fetchval.return_value = None  # no duplicate event
        conn.fetchrow.side_effect = [
            FakeRecord(id=uuid.uuid4()),  # customer lookup
            FakeRecord(id=uuid.uuid4()),  # subscription lookup for event recording
        ]

        event_payload = {
            "id": "evt_test_123",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_456",
                    "status": "active",
                    "metadata": {"tier": "pro"},
                    "current_period_start": 1710806400,
                    "current_period_end": 1713398400,
                }
            },
        }

        resp = tc.post(
            "/webhook",
            content=json.dumps(event_payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "processed"

    def test_webhook_duplicate_event(self, client):
        tc, conn, _ = client
        conn.fetchval.return_value = uuid.uuid4()  # event already exists

        event_payload = {
            "id": "evt_duplicate",
            "type": "customer.subscription.created",
            "data": {"object": {"id": "sub_1"}},
        }

        resp = tc.post(
            "/webhook",
            content=json.dumps(event_payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "already_processed"

    def test_webhook_payment_failed(self, client):
        tc, conn, _ = client
        conn.fetchval.return_value = None
        conn.fetchrow.return_value = FakeRecord(id=uuid.uuid4())

        event_payload = {
            "id": "evt_pay_fail",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_test",
                    "subscription": "sub_test_789",
                }
            },
        }

        resp = tc.post(
            "/webhook",
            content=json.dumps(event_payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200


class TestPortal:
    @patch("services.billing.app.stripe")
    def test_portal_success(self, mock_stripe, client):
        tc, conn, _ = client
        mock_stripe.api_key = "sk-test"
        conn.fetchrow.return_value = FakeRecord(stripe_customer_id="cus_test")
        mock_session = MagicMock()
        mock_session.url = "https://billing.stripe.com/portal/test"
        mock_stripe.billing_portal.Session.create.return_value = mock_session

        resp = tc.post("/portal", json={
            "customer_id": str(uuid.uuid4()),
            "return_url": "https://tradestream.io/account",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "portal_url" in body["data"]["attributes"]

    def test_portal_customer_not_found(self, client):
        tc, conn, _ = client
        conn.fetchrow.return_value = None

        resp = tc.post("/portal", json={
            "customer_id": str(uuid.uuid4()),
            "return_url": "https://tradestream.io/account",
        })
        assert resp.status_code == 404
