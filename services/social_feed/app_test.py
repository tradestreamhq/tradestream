"""Tests for the Strategy Sharing & Social Feed REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from services.social_feed.app import create_app


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


# ---------------------------------------------------------------------------
# Share Strategy
# ---------------------------------------------------------------------------


class TestShareStrategy:
    def test_share_strategy_success(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        shared_id = uuid.uuid4()

        # First call: check spec exists; second call: insert
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id),
            FakeRecord(
                id=shared_id,
                strategy_id=strategy_id,
                author_id="user1",
                author_name="Alice",
                caption="My best strategy",
                like_count=0,
                comment_count=0,
                shared_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/strategies/{strategy_id}/share",
            json={
                "author_id": "user1",
                "author_name": "Alice",
                "caption": "My best strategy",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(shared_id)
        assert body["data"]["attributes"]["author_name"] == "Alice"

    def test_share_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/share",
            json={"author_id": "user1"},
        )
        assert resp.status_code == 404

    def test_share_strategy_already_shared(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id),
            asyncpg.UniqueViolationError("duplicate"),
        ]

        # Make the second fetchrow raise UniqueViolationError
        call_count = 0
        original_side_effect = conn.fetchrow.side_effect

        async def mock_fetchrow(*args, **kwargs):
            nonlocal call_count
            result = original_side_effect[call_count]
            call_count += 1
            if isinstance(result, Exception):
                raise result
            return result

        conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)

        resp = tc.post(
            f"/strategies/{strategy_id}/share",
            json={"author_id": "user1"},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------


class TestFeed:
    def test_list_feed(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=shared_id,
                strategy_id=strategy_id,
                author_id="user1",
                author_name="Alice",
                caption="Check this out",
                like_count=5,
                comment_count=2,
                shared_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                strategy_name="macd_cross",
                strategy_description="MACD crossover strategy",
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/feed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "shared_strategy"
        assert body["data"][0]["attributes"]["author_name"] == "Alice"

    def test_list_feed_with_author_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/feed?author_id=user2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_list_feed_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 50

        resp = tc.get("/feed?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20
        assert body["meta"]["total"] == 50


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------


class TestLikes:
    def test_like_strategy(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()

        # First fetchrow: shared exists; second: no existing like
        conn.fetchrow.side_effect = [
            FakeRecord(id=shared_id),
            None,
        ]

        resp = tc.post(
            f"/feed/{shared_id}/like",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["liked"] is True

    def test_unlike_strategy(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()
        like_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=shared_id),
            FakeRecord(id=like_id),
        ]

        resp = tc.post(
            f"/feed/{shared_id}/like",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["liked"] is False

    def test_like_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/feed/{uuid.uuid4()}/like",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class TestComments:
    def test_add_comment(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            FakeRecord(id=shared_id),
            FakeRecord(
                id=comment_id,
                shared_strategy_id=shared_id,
                user_id="user1",
                user_name="Alice",
                body="Great strategy!",
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/feed/{shared_id}/comment",
            json={
                "user_id": "user1",
                "user_name": "Alice",
                "body": "Great strategy!",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(comment_id)
        assert body["data"]["attributes"]["body"] == "Great strategy!"

    def test_add_comment_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/feed/{uuid.uuid4()}/comment",
            json={"user_id": "user1", "body": "hello"},
        )
        assert resp.status_code == 404

    def test_add_comment_empty_body(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()

        resp = tc.post(
            f"/feed/{shared_id}/comment",
            json={"user_id": "user1", "body": ""},
        )
        assert resp.status_code == 422

    def test_list_comments(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        conn.fetchrow.return_value = FakeRecord(id=shared_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=comment_id,
                shared_strategy_id=shared_id,
                user_id="user1",
                user_name="Alice",
                body="Nice!",
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/feed/{shared_id}/comments")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["attributes"]["body"] == "Nice!"

    def test_list_comments_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/feed/{uuid.uuid4()}/comments")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Follow System
# ---------------------------------------------------------------------------


class TestFollowSystem:
    def test_follow_user(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None  # No existing follow

        resp = tc.post(
            "/users/user2/follow",
            json={"follower_id": "user1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["following"] is True
        assert body["data"]["attributes"]["followed_id"] == "user2"

    def test_unfollow_user(self, client):
        tc, conn = client
        follow_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=follow_id)

        resp = tc.post(
            "/users/user2/follow",
            json={"follower_id": "user1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["following"] is False

    def test_follow_self(self, client):
        tc, conn = client

        resp = tc.post(
            "/users/user1/follow",
            json={"follower_id": "user1"},
        )
        assert resp.status_code == 422

    def test_following_feed(self, client):
        tc, conn = client
        shared_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=shared_id,
                strategy_id=strategy_id,
                author_id="user2",
                author_name="Bob",
                caption="My strategy",
                like_count=3,
                comment_count=1,
                shared_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                strategy_name="rsi_bounce",
                strategy_description="RSI bounce strategy",
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/feed/following?user_id=user1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["attributes"]["author_id"] == "user2"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "social-feed-api"
