"""Tests for the Webhook REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.webhook_api.app import create_app


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


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "webhook-api"


class TestCreateWebhook:
    def test_create_webhook_success(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            events=["trade.executed", "alert.triggered"],
            is_active=True,
            description="My webhook",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": ["trade.executed", "alert.triggered"],
                "secret": "my-secret",
                "description": "My webhook",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(webhook_id)
        assert body["data"]["type"] == "webhook"
        assert body["data"]["attributes"]["url"] == "https://example.com/hook"
        assert "trade.executed" in body["data"]["attributes"]["events"]

    def test_create_webhook_invalid_event(self, client):
        tc, conn = client
        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": ["invalid.event"],
                "secret": "my-secret",
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "invalid.event" in body["error"]["message"]

    def test_create_webhook_empty_events(self, client):
        tc, conn = client
        resp = tc.post(
            "/",
            json={
                "url": "https://example.com/hook",
                "events": [],
                "secret": "my-secret",
            },
        )
        assert resp.status_code == 422

    def test_create_webhook_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/", json={"url": "https://example.com/hook"})
        assert resp.status_code == 422


class TestListWebhooks:
    def test_list_webhooks(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=webhook_id,
                url="https://example.com/hook",
                events=["trade.executed"],
                is_active=True,
                description="Test",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "webhook"

    def test_list_webhooks_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert len(body["data"]) == 0

    def test_list_webhooks_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/?limit=10&offset=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 5


class TestDeleteWebhook:
    def test_delete_webhook_success(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=webhook_id)

        resp = tc.delete(f"/{webhook_id}")
        assert resp.status_code == 204

    def test_delete_webhook_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTestWebhook:
    def test_test_webhook_success(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            secret="test-secret",
            events=["trade.executed"],
        )

        with patch(
            "services.webhook_api.app.deliver_webhook",
            return_value={
                "success": True,
                "status_code": 200,
                "response_body": "OK",
                "error": None,
            },
        ):
            resp = tc.post(f"/{webhook_id}/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["delivered"] is True
        assert body["data"]["attributes"]["status_code"] == 200

    def test_test_webhook_delivery_failure(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=webhook_id,
            url="https://example.com/hook",
            secret="test-secret",
            events=["trade.executed"],
        )

        with patch(
            "services.webhook_api.app.deliver_webhook",
            return_value={
                "success": False,
                "status_code": 500,
                "response_body": "error",
                "error": "HTTP 500",
            },
        ):
            resp = tc.post(f"/{webhook_id}/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["delivered"] is False

    def test_test_webhook_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(f"/{uuid.uuid4()}/test")
        assert resp.status_code == 404


class TestListDeliveries:
    def test_list_deliveries(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        delivery_id = uuid.uuid4()

        # First call: fetchval for webhook existence check
        # Second call: fetch for delivery rows
        # Third call: fetchval for count
        conn.fetchval.side_effect = [1, 1]
        conn.fetch.return_value = [
            FakeRecord(
                id=delivery_id,
                webhook_id=webhook_id,
                event_type="trade.executed",
                status="success",
                attempts=1,
                response_code=200,
                error_message=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get(f"/{webhook_id}/deliveries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["status"] == "success"

    def test_list_deliveries_webhook_not_found(self, client):
        tc, conn = client
        conn.fetchval.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}/deliveries")
        assert resp.status_code == 404

    def test_list_deliveries_empty(self, client):
        tc, conn = client
        webhook_id = uuid.uuid4()
        conn.fetchval.side_effect = [1, 0]
        conn.fetch.return_value = []

        resp = tc.get(f"/{webhook_id}/deliveries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
