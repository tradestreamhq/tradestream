"""Tests for the Webhook REST API and dispatcher."""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.webhook_api.app import create_app
from services.webhook_api.dispatcher import WebhookDispatcher, compute_signature


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


# ---------------------------------------------------------------------------
# HMAC Signing Tests
# ---------------------------------------------------------------------------


class TestSignature:
    def test_compute_signature_deterministic(self):
        secret = "test-secret"
        timestamp = "1700000000"
        payload = '{"event":"test"}'

        sig1 = compute_signature(secret, timestamp, payload)
        sig2 = compute_signature(secret, timestamp, payload)
        assert sig1 == sig2

    def test_compute_signature_matches_hmac(self):
        secret = "my-secret"
        timestamp = "1700000000"
        payload = '{"data":"hello"}'

        expected = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.{payload}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert compute_signature(secret, timestamp, payload) == expected

    def test_different_secrets_produce_different_signatures(self):
        timestamp = "1700000000"
        payload = '{"event":"test"}'

        sig1 = compute_signature("secret-a", timestamp, payload)
        sig2 = compute_signature("secret-b", timestamp, payload)
        assert sig1 != sig2

    def test_different_payloads_produce_different_signatures(self):
        secret = "test-secret"
        timestamp = "1700000000"

        sig1 = compute_signature(secret, timestamp, '{"a":1}')
        sig2 = compute_signature(secret, timestamp, '{"b":2}')
        assert sig1 != sig2


# ---------------------------------------------------------------------------
# Webhook CRUD Tests
# ---------------------------------------------------------------------------


class TestCreateWebhook:
    def test_create_webhook_success(self, client):
        tc, conn, pool = client
        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": ["signal_generated", "trade_executed"],
                "description": "My test webhook",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "webhook"
        assert body["data"]["attributes"]["url"] == "https://example.com/hook"
        assert "signing_secret" in body["data"]["attributes"]
        assert len(body["data"]["attributes"]["signing_secret"]) == 64
        conn.execute.assert_called_once()

    def test_create_webhook_invalid_event(self, client):
        tc, conn, pool = client
        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": ["invalid_event"],
            },
        )
        assert resp.status_code == 422

    def test_create_webhook_empty_events(self, client):
        tc, conn, pool = client
        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": [],
            },
        )
        assert resp.status_code == 422

    def test_create_webhook_invalid_url(self, client):
        tc, conn, pool = client
        resp = tc.post(
            "/",
            json={
                "url": "not-a-url",
                "events": ["signal_generated"],
            },
        )
        assert resp.status_code == 422


class TestListWebhooks:
    def test_list_webhooks_empty(self, client):
        tc, conn, pool = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_list_webhooks_with_results(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            FakeRecord(
                id=webhook_id,
                url="https://example.com/hook",
                events=["signal_generated"],
                description="Test",
                is_active=True,
                signing_secret="abc123",
                created_at=now,
                updated_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "webhook"
        assert body["meta"]["total"] == 1


class TestGetWebhook:
    def test_get_webhook_found(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            events=["signal_generated"],
            description="Test",
            is_active=True,
            signing_secret="abc123",
            created_at=now,
            updated_at=now,
        )

        resp = tc.get(f"/{webhook_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == str(webhook_id)

    def test_get_webhook_not_found(self, client):
        tc, conn, pool = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateWebhook:
    def test_update_webhook_success(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # First call: check existence; second call: RETURNING
        conn.fetchrow.side_effect = [
            FakeRecord(id=webhook_id),
            FakeRecord(
                id=webhook_id,
                url="https://new.example.com/hook",
                events=["trade_executed"],
                description="Updated",
                is_active=True,
                signing_secret="abc123",
                created_at=now,
                updated_at=now,
            ),
        ]

        resp = tc.put(
            f"/{webhook_id}",
            json={
                "url": "https://new.example.com/hook",
                "description": "Updated",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["url"] == "https://new.example.com/hook"

    def test_update_webhook_not_found(self, client):
        tc, conn, pool = client
        conn.fetchrow.return_value = None

        resp = tc.put(
            f"/{uuid.uuid4()}",
            json={"description": "Updated"},
        )
        assert resp.status_code == 404

    def test_update_webhook_no_fields(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=webhook_id)

        resp = tc.put(f"/{webhook_id}", json={})
        assert resp.status_code == 422


class TestDeleteWebhook:
    def test_delete_webhook_success(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=webhook_id)

        resp = tc.delete(f"/{webhook_id}")
        assert resp.status_code == 204

    def test_delete_webhook_not_found(self, client):
        tc, conn, pool = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTestWebhook:
    @patch("services.webhook_api.dispatcher._send_with_retries")
    def test_test_webhook_success(self, mock_send, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        mock_send.return_value = 200

        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            signing_secret="secret",
        )

        resp = tc.post(f"/{webhook_id}/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["success"] is True

    def test_test_webhook_not_found(self, client):
        tc, conn, pool = client
        conn.fetchrow.return_value = None

        resp = tc.post(f"/{uuid.uuid4()}/test")
        assert resp.status_code == 404


class TestDeliveryHistory:
    def test_list_deliveries(self, client):
        tc, conn, pool = client
        webhook_id = uuid.uuid4()
        delivery_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        conn.fetchrow.return_value = FakeRecord(id=webhook_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=delivery_id,
                webhook_id=webhook_id,
                event_type="signal_generated",
                status="success",
                response_code=200,
                error_message=None,
                created_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/{webhook_id}/deliveries")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["status"] == "success"

    def test_list_deliveries_webhook_not_found(self, client):
        tc, conn, pool = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}/deliveries")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dispatcher Tests
# ---------------------------------------------------------------------------


class TestDispatcher:
    @pytest.fixture
    def dispatcher(self):
        pool, conn = _make_pool()
        return WebhookDispatcher(pool), conn

    @patch("services.webhook_api.dispatcher._send_with_retries")
    @pytest.mark.asyncio
    async def test_dispatch_event_to_matching_webhooks(self, mock_send, dispatcher):
        disp, conn = dispatcher
        webhook_id = uuid.uuid4()
        mock_send.return_value = 200

        conn.fetch.return_value = [
            FakeRecord(
                id=webhook_id,
                url="https://example.com/hook",
                signing_secret="secret",
            )
        ]

        results = await disp.dispatch_event(
            "signal_generated", {"signal": "BUY", "instrument": "BTC/USD"}
        )

        assert len(results) == 1
        assert results[0]["success"] is True
        mock_send.assert_called_once()
        # Verify delivery was logged
        conn.execute.assert_called_once()

    @patch("services.webhook_api.dispatcher._send_with_retries")
    @pytest.mark.asyncio
    async def test_dispatch_event_no_matching_webhooks(self, mock_send, dispatcher):
        disp, conn = dispatcher
        conn.fetch.return_value = []

        results = await disp.dispatch_event(
            "trade_executed", {"trade": "SELL"}
        )

        assert len(results) == 0
        mock_send.assert_not_called()

    @patch("services.webhook_api.dispatcher._send_with_retries")
    @pytest.mark.asyncio
    async def test_dispatch_event_delivery_failure(self, mock_send, dispatcher):
        disp, conn = dispatcher
        webhook_id = uuid.uuid4()
        mock_send.side_effect = Exception("Connection refused")

        conn.fetch.return_value = [
            FakeRecord(
                id=webhook_id,
                url="https://example.com/hook",
                signing_secret="secret",
            )
        ]

        results = await disp.dispatch_event(
            "alert_triggered", {"alert": "price_drop"}
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "Connection refused" in results[0]["error"]

    @patch("services.webhook_api.dispatcher._send_with_retries")
    @pytest.mark.asyncio
    async def test_send_test(self, mock_send, dispatcher):
        disp, conn = dispatcher
        webhook_id = uuid.uuid4()
        mock_send.return_value = 200

        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            signing_secret="test-secret",
        )

        result = await disp.send_test(webhook_id)
        assert result["success"] is True
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_webhook_not_found(self, dispatcher):
        disp, conn = dispatcher
        conn.fetchrow.return_value = None

        result = await disp.send_test(uuid.uuid4())
        assert result["success"] is False
        assert result["error"] == "Webhook not found"


# ---------------------------------------------------------------------------
# Retry Logic Tests
# ---------------------------------------------------------------------------


class TestRetryLogic:
    @patch("services.webhook_api.dispatcher.requests.post")
    def test_successful_delivery_no_retry(self, mock_post):
        from services.webhook_api.dispatcher import _send_with_retries

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = _send_with_retries(
            "https://example.com", '{"test":true}', {"Content-Type": "application/json"}
        )
        assert result == 200
        assert mock_post.call_count == 1

    @patch("services.webhook_api.dispatcher.requests.post")
    def test_server_error_triggers_retry(self, mock_post):
        from services.webhook_api.dispatcher import _send_with_retries

        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_resp_fail.text = "Internal Server Error"

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200

        mock_post.side_effect = [mock_resp_fail, mock_resp_ok]

        result = _send_with_retries(
            "https://example.com", '{"test":true}', {"Content-Type": "application/json"}
        )
        assert result == 200
        assert mock_post.call_count == 2

    @patch("services.webhook_api.dispatcher.requests.post")
    def test_three_failures_raises(self, mock_post):
        from requests import RequestException

        from services.webhook_api.dispatcher import _send_with_retries

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        mock_post.return_value = mock_resp

        with pytest.raises(RequestException):
            _send_with_retries(
                "https://example.com",
                '{"test":true}',
                {"Content-Type": "application/json"},
            )
        assert mock_post.call_count == 3
