"""Tests for the Watchlist & Favorites REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from services.watchlist_api.app import create_app


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


# --- Health ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "watchlist-api"


# --- Watchlist CRUD ---


class TestWatchlistEndpoints:
    def test_list_watchlists(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetch.return_value = [
            FakeRecord(
                id=wl_id,
                name="Top Crypto",
                pairs=["BTC/USD", "ETH/USD"],
                alert_conditions=None,
                created_at=now,
                updated_at=now,
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/watchlists")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "watchlist"
        assert body["data"][0]["attributes"]["name"] == "Top Crypto"

    def test_create_watchlist(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=wl_id,
            name="My Watchlist",
            pairs=["BTC/USD"],
            alert_conditions=None,
            created_at=now,
            updated_at=now,
        )

        resp = tc.post(
            "/watchlists",
            json={"name": "My Watchlist", "pairs": ["BTC/USD"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(wl_id)
        assert body["data"]["attributes"]["name"] == "My Watchlist"

    def test_create_watchlist_duplicate(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = asyncpg.UniqueViolationError("")

        resp = tc.post(
            "/watchlists",
            json={"name": "Dup", "pairs": []},
        )
        assert resp.status_code == 409

    def test_create_watchlist_missing_name(self, client):
        tc, conn = client
        resp = tc.post("/watchlists", json={"pairs": ["BTC/USD"]})
        assert resp.status_code == 422

    def test_get_watchlist(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=wl_id,
            name="WL1",
            pairs=["ETH/USD"],
            alert_conditions={"price_above": 5000},
            created_at=now,
            updated_at=now,
        )

        resp = tc.get(f"/watchlists/{wl_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "WL1"
        assert body["data"]["attributes"]["pairs"] == ["ETH/USD"]

    def test_get_watchlist_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/watchlists/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_watchlist(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=wl_id,
            name="Updated",
            pairs=["BTC/USD", "SOL/USD"],
            alert_conditions=None,
            created_at=now,
            updated_at=now,
        )

        resp = tc.put(
            f"/watchlists/{wl_id}",
            json={"name": "Updated", "pairs": ["BTC/USD", "SOL/USD"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "Updated"

    def test_update_watchlist_no_fields(self, client):
        tc, conn = client
        resp = tc.put(f"/watchlists/{uuid.uuid4()}", json={})
        assert resp.status_code == 422

    def test_update_watchlist_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.put(
            f"/watchlists/{uuid.uuid4()}",
            json={"name": "New Name"},
        )
        assert resp.status_code == 404

    def test_update_watchlist_duplicate_name(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = asyncpg.UniqueViolationError("")

        resp = tc.put(
            f"/watchlists/{uuid.uuid4()}",
            json={"name": "Existing"},
        )
        assert resp.status_code == 409

    def test_delete_watchlist(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=wl_id)

        resp = tc.delete(f"/watchlists/{wl_id}")
        assert resp.status_code == 204

    def test_delete_watchlist_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/watchlists/{uuid.uuid4()}")
        assert resp.status_code == 404


# --- Widget ---


class TestWidgetEndpoint:
    def test_widget_returns_pairs(self, client):
        tc, conn = client
        wl_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=wl_id,
            name="Dashboard WL",
            pairs=["BTC/USD", "ETH/USD"],
        )

        resp = tc.get(f"/watchlists/widget?watchlist_id={wl_id}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["watchlist_name"] == "Dashboard WL"
        assert len(attrs["pairs"]) == 2
        assert attrs["pairs"][0]["pair"] == "BTC/USD"
        assert attrs["pairs"][0]["current_price"] is None

    def test_widget_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/watchlists/widget?watchlist_id={uuid.uuid4()}")
        assert resp.status_code == 404

    def test_widget_missing_param(self, client):
        tc, conn = client
        resp = tc.get("/watchlists/widget")
        assert resp.status_code == 422


# --- Favorites ---


class TestFavoritesEndpoints:
    def test_list_favorites_grouped(self, client):
        tc, conn = client
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                entity_type="strategies",
                entity_id="strat-1",
                created_at=now,
            ),
            FakeRecord(
                id=uuid.uuid4(),
                entity_type="strategies",
                entity_id="strat-2",
                created_at=now,
            ),
            FakeRecord(
                id=uuid.uuid4(),
                entity_type="pairs",
                entity_id="BTC/USD",
                created_at=now,
            ),
        ]

        resp = tc.get("/favorites")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["strategies"]) == 2
        assert len(attrs["pairs"]) == 1

    def test_add_favorite(self, client):
        tc, conn = client
        fav_id = uuid.uuid4()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        conn.fetchrow.return_value = FakeRecord(
            id=fav_id,
            entity_type="strategies",
            entity_id="strat-1",
            created_at=now,
        )

        resp = tc.post("/favorites/strategies/strat-1")
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(fav_id)

    def test_add_favorite_invalid_type(self, client):
        tc, conn = client
        resp = tc.post("/favorites/invalid_type/some-id")
        assert resp.status_code == 422

    def test_add_favorite_duplicate(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = asyncpg.UniqueViolationError("")

        resp = tc.post("/favorites/pairs/BTC-USD")
        assert resp.status_code == 409

    def test_remove_favorite(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(id=uuid.uuid4())

        resp = tc.delete("/favorites/strategies/strat-1")
        assert resp.status_code == 204

    def test_remove_favorite_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete("/favorites/strategies/nonexistent")
        assert resp.status_code == 404
