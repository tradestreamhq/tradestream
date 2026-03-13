"""Tests for the Notification Preferences & Delivery API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.notification_preferences_api.app import (
    NotificationDeliveryService,
    create_app,
)


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


def _make_transaction(conn):
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = txn
    return txn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    _make_transaction(conn)
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


USER_ID = "user-123"


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestGetPreferences:
    def test_returns_defaults_when_no_prefs_stored(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/notification-preferences", params={"user_id": USER_ID})
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["user_id"] == USER_ID
        # All event types should have default in_app channel
        prefs = {p["event_type"]: p["channels"] for p in attrs["preferences"]}
        assert prefs["signal_generated"] == ["in_app"]
        assert prefs["trade_executed"] == ["in_app"]

    def test_returns_stored_prefs(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(event_type="signal_generated", channels=["in_app", "email"]),
            FakeRecord(event_type="trade_executed", channels=["webhook"]),
        ]

        resp = tc.get("/notification-preferences", params={"user_id": USER_ID})
        assert resp.status_code == 200
        body = resp.json()
        prefs = {
            p["event_type"]: p["channels"]
            for p in body["data"]["attributes"]["preferences"]
        }
        assert prefs["signal_generated"] == ["in_app", "email"]
        assert prefs["trade_executed"] == ["webhook"]

    def test_requires_user_id(self, client):
        tc, _ = client
        resp = tc.get("/notification-preferences")
        assert resp.status_code == 422


class TestUpdatePreferences:
    def test_update_preferences(self, client):
        tc, conn = client
        # After update, the GET will fetch the stored prefs
        conn.fetch.return_value = [
            FakeRecord(event_type="signal_generated", channels=["email", "webhook"]),
        ]

        resp = tc.put(
            "/notification-preferences",
            params={"user_id": USER_ID},
            json={
                "preferences": [
                    {
                        "event_type": "signal_generated",
                        "channels": ["email", "webhook"],
                    }
                ]
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == USER_ID

        # Verify DELETE + INSERT were called
        calls = conn.execute.call_args_list
        assert any("DELETE" in str(c) for c in calls)
        assert any("INSERT" in str(c) for c in calls)

    def test_rejects_empty_channels(self, client):
        tc, conn = client
        resp = tc.put(
            "/notification-preferences",
            params={"user_id": USER_ID},
            json={
                "preferences": [
                    {"event_type": "signal_generated", "channels": []}
                ]
            },
        )
        assert resp.status_code == 422

    def test_rejects_invalid_event_type(self, client):
        tc, conn = client
        resp = tc.put(
            "/notification-preferences",
            params={"user_id": USER_ID},
            json={
                "preferences": [
                    {"event_type": "invalid_event", "channels": ["in_app"]}
                ]
            },
        )
        assert resp.status_code == 422

    def test_rejects_invalid_channel(self, client):
        tc, conn = client
        resp = tc.put(
            "/notification-preferences",
            params={"user_id": USER_ID},
            json={
                "preferences": [
                    {"event_type": "signal_generated", "channels": ["sms"]}
                ]
            },
        )
        assert resp.status_code == 422


class TestListNotifications:
    def test_list_notifications_paginated(self, client):
        tc, conn = client
        now = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)
        notif_id = str(uuid.uuid4())
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=notif_id,
                user_id=USER_ID,
                event_type="signal_generated",
                title="BTC Buy Signal",
                body="High confidence buy signal for BTC/USD",
                metadata=None,
                is_read=False,
                created_at=now,
            )
        ]

        resp = tc.get(
            "/notifications",
            params={"user_id": USER_ID, "limit": 10, "offset": 0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 0
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["title"] == "BTC Buy Signal"

    def test_list_empty(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("/notifications", params={"user_id": USER_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert len(body["data"]) == 0


class TestMarkRead:
    def test_mark_notification_read(self, client):
        tc, conn = client
        notif_id = str(uuid.uuid4())
        now = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=notif_id,
            user_id=USER_ID,
            event_type="signal_generated",
            title="BTC Buy Signal",
            body="High confidence buy signal",
            metadata=None,
            is_read=True,
            created_at=now,
        )

        resp = tc.put(f"/notifications/{notif_id}/read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["is_read"] is True

    def test_mark_read_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.put(f"/notifications/{uuid.uuid4()}/read")
        assert resp.status_code == 404


class TestUnreadCount:
    def test_unread_count(self, client):
        tc, conn = client
        conn.fetchval.return_value = 5

        resp = tc.get("/notifications/unread-count", params={"user_id": USER_ID})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["unread_count"] == 5

    def test_unread_count_zero(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0

        resp = tc.get("/notifications/unread-count", params={"user_id": USER_ID})
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["unread_count"] == 0


class TestNotificationDeliveryService:
    @pytest.mark.asyncio
    async def test_deliver_in_app(self):
        pool, conn = _make_pool()
        service = NotificationDeliveryService(pool)

        # Preferences: in_app only
        conn.fetch.return_value = [
            FakeRecord(event_type="signal_generated", channels=["in_app"]),
        ]

        results = await service.deliver(
            user_id=USER_ID,
            event_type="signal_generated",
            title="Test",
            body="Test body",
        )
        assert results["in_app"] is True
        # Verify INSERT was called for in-app storage
        conn.execute.assert_called_once()
        insert_call = conn.execute.call_args
        assert "INSERT INTO notifications" in insert_call[0][0]

    @pytest.mark.asyncio
    async def test_deliver_multiple_channels(self):
        pool, conn = _make_pool()
        service = NotificationDeliveryService(pool)

        conn.fetch.return_value = [
            FakeRecord(
                event_type="trade_executed",
                channels=["in_app", "email", "webhook"],
            ),
        ]

        results = await service.deliver(
            user_id=USER_ID,
            event_type="trade_executed",
            title="Trade Executed",
            body="BTC/USD buy executed",
        )
        assert results["in_app"] is True
        assert results["email"] is True
        assert results["webhook"] is True

    @pytest.mark.asyncio
    async def test_deliver_uses_defaults_when_no_prefs(self):
        pool, conn = _make_pool()
        service = NotificationDeliveryService(pool)

        conn.fetch.return_value = []  # No stored preferences

        results = await service.deliver(
            user_id=USER_ID,
            event_type="signal_generated",
            title="Test",
            body="Test body",
        )
        # Default is in_app
        assert results["in_app"] is True

    @pytest.mark.asyncio
    async def test_deliver_handles_channel_failure(self):
        pool, conn = _make_pool()
        service = NotificationDeliveryService(pool)

        conn.fetch.return_value = [
            FakeRecord(event_type="signal_generated", channels=["in_app"]),
        ]
        conn.execute.side_effect = Exception("DB error")

        results = await service.deliver(
            user_id=USER_ID,
            event_type="signal_generated",
            title="Test",
            body="Test body",
        )
        assert results["in_app"] is False
