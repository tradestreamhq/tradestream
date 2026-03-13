"""Tests for the Strategy Marketplace REST API."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.marketplace_api.app import create_app


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


def _fake_listing(listing_id=None, strategy_id=None):
    return FakeRecord(
        id=listing_id or uuid.uuid4(),
        strategy_id=strategy_id or uuid.uuid4(),
        author="test_author",
        description="A great strategy",
        performance_stats={"sharpe_ratio": 1.8},
        price=9.99,
        subscribers_count=5,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "marketplace-api"


class TestPublishEndpoint:
    def test_publish_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = _fake_listing(listing_id, strategy_id)

        resp = tc.post(
            "/",
            json={
                "strategy_id": str(strategy_id),
                "author": "test_author",
                "description": "A great strategy",
                "performance_stats": {"sharpe_ratio": 1.8},
                "price": 9.99,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(listing_id)
        assert body["data"]["attributes"]["author"] == "test_author"

    def test_publish_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/", json={"author": "me"})
        assert resp.status_code == 422

    def test_publish_duplicate(self, client):
        tc, conn = client
        import asyncpg

        conn.fetchrow.side_effect = asyncpg.UniqueViolationError("")

        resp = tc.post(
            "/",
            json={
                "strategy_id": str(uuid.uuid4()),
                "author": "test_author",
                "description": "Dup",
                "price": 0,
            },
        )
        assert resp.status_code == 409


class TestBrowseEndpoint:
    def test_list_listings(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetch.return_value = [_fake_listing(listing_id)]
        conn.fetchval.return_value = 1

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "marketplace_listing"

    def test_list_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/?author=alice&min_price=5&max_price=100")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_list_with_order_by(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/?order_by=subscribers_count")
        assert resp.status_code == 200


class TestGetListingEndpoint:
    def test_get_listing_found(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            _fake_listing(listing_id),
            FakeRecord(avg_score=4.5, rating_count=10),
        ]

        resp = tc.get(f"/{listing_id}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["author"] == "test_author"
        assert attrs["avg_rating"] == 4.5
        assert attrs["rating_count"] == 10

    def test_get_listing_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestSubscribeEndpoints:
    def test_subscribe_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),  # listing exists check
            FakeRecord(
                id=sub_id,
                listing_id=listing_id,
                user_id="user1",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),  # insert
        ]

        resp = tc.post(
            f"/{listing_id}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["user_id"] == "user1"

    def test_subscribe_listing_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/{uuid.uuid4()}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 404

    def test_subscribe_duplicate(self, client):
        tc, conn = client
        import asyncpg

        listing_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),  # listing exists
            asyncpg.UniqueViolationError(""),  # duplicate subscription
        ]

        resp = tc.post(
            f"/{listing_id}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 409

    def test_unsubscribe_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=uuid.uuid4())

        resp = tc.delete(f"/{listing_id}/subscribe?user_id=user1")
        assert resp.status_code == 204

    def test_unsubscribe_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/{uuid.uuid4()}/subscribe?user_id=user1")
        assert resp.status_code == 404


class TestRatingEndpoints:
    def test_rate_listing_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        rating_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),  # listing exists
            FakeRecord(
                id=rating_id,
                listing_id=listing_id,
                user_id="user1",
                score=5,
                review="Excellent!",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/{listing_id}/rate",
            json={"user_id": "user1", "score": 5, "review": "Excellent!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["score"] == 5

    def test_rate_listing_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/{uuid.uuid4()}/rate",
            json={"user_id": "user1", "score": 3},
        )
        assert resp.status_code == 404

    def test_rate_invalid_score(self, client):
        tc, conn = client
        resp = tc.post(
            f"/{uuid.uuid4()}/rate",
            json={"user_id": "user1", "score": 6},
        )
        assert resp.status_code == 422

    def test_list_ratings(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        rating_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=listing_id)  # listing exists
        conn.fetch.return_value = [
            FakeRecord(
                id=rating_id,
                listing_id=listing_id,
                user_id="user1",
                score=4,
                review="Good",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/{listing_id}/ratings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["attributes"]["score"] == 4

    def test_list_ratings_listing_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}/ratings")
        assert resp.status_code == 404
