"""Tests for the Strategy Marketplace & Leaderboard API."""

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_marketplace_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

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
    return TestClient(app, raise_server_exceptions=False), conn


def _fake_listing(listing_id=None, strategy_id=None, category="momentum"):
    return FakeRecord(
        id=listing_id or uuid.uuid4(),
        strategy_id=strategy_id or uuid.uuid4(),
        name="MACD Crossover",
        author="test_author",
        description="A momentum strategy",
        category=category,
        tags=["crypto", "momentum"],
        performance_stats={"sharpe_ratio": 1.8},
        price=9.99,
        subscribers_count=5,
        avg_rating=4.2,
        rating_count=10,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _fake_snapshot(strategy_id=None, period="monthly"):
    return FakeRecord(
        strategy_id=strategy_id or uuid.uuid4(),
        period=period,
        rank=1,
        total_return_pct=42.5,
        sharpe_ratio=2.1,
        win_rate=0.68,
        max_drawdown_pct=-12.3,
        trade_count=150,
        consistency_score=0.85,
        snapshot_date=date(2026, 3, 1),
        name="MACD Crossover",
        category="momentum",
        author="test_author",
    )


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-marketplace-api"


# ===================================================================
# Marketplace Catalog
# ===================================================================


class TestPublishStrategy:
    def test_publish_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = _fake_listing(listing_id, strategy_id)

        resp = tc.post(
            "/strategies",
            json={
                "strategy_id": str(strategy_id),
                "name": "MACD Crossover",
                "author": "test_author",
                "description": "A momentum strategy",
                "category": "momentum",
                "tags": ["crypto", "momentum"],
                "performance_stats": {"sharpe_ratio": 1.8},
                "price": 9.99,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(listing_id)
        assert body["data"]["attributes"]["name"] == "MACD Crossover"
        assert body["data"]["attributes"]["category"] == "momentum"

    def test_publish_invalid_category(self, client):
        tc, conn = client
        resp = tc.post(
            "/strategies",
            json={
                "strategy_id": str(uuid.uuid4()),
                "name": "Bad Cat",
                "author": "test",
                "category": "invalid_cat",
            },
        )
        assert resp.status_code == 422

    def test_publish_duplicate(self, client):
        tc, conn = client
        import asyncpg

        conn.fetchrow.side_effect = asyncpg.UniqueViolationError("")
        resp = tc.post(
            "/strategies",
            json={
                "strategy_id": str(uuid.uuid4()),
                "name": "Dup",
                "author": "test",
                "category": "momentum",
            },
        )
        assert resp.status_code == 409

    def test_publish_missing_fields(self, client):
        tc, conn = client
        resp = tc.post("/strategies", json={"author": "me"})
        assert resp.status_code == 422


class TestListStrategies:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetch.return_value = [_fake_listing()]
        conn.fetchval.return_value = 1

        resp = tc.get("/strategies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "marketplace_listing"

    def test_list_by_category(self, client):
        tc, conn = client
        conn.fetch.return_value = [_fake_listing(category="breakout")]
        conn.fetchval.return_value = 1

        resp = tc.get("/strategies?category=breakout")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["attributes"]["category"] == "breakout"

    def test_list_with_search(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?search=macd")
        assert resp.status_code == 200

    def test_list_with_tags(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?tags=crypto,momentum")
        assert resp.status_code == 200

    def test_list_with_price_range(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?min_price=5&max_price=100")
        assert resp.status_code == 200

    def test_list_order_by_rating(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/strategies?order_by=avg_rating")
        assert resp.status_code == 200


class TestGetStrategy:
    def test_get_found(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            _fake_listing(listing_id, strategy_id),
            FakeRecord(
                total_return_pct=42.5,
                sharpe_ratio=2.1,
                win_rate=0.68,
                max_drawdown_pct=-12.3,
                trade_count=150,
                consistency_score=0.85,
                snapshot_date=date(2026, 3, 1),
            ),
        ]

        resp = tc.get(f"/strategies/{listing_id}")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["name"] == "MACD Crossover"
        assert attrs["live_metrics"]["sharpe_ratio"] == 2.1
        assert attrs["live_metrics"]["trade_count"] == 150

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_without_perf_data(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            _fake_listing(listing_id),
            None,  # no leaderboard data
        ]

        resp = tc.get(f"/strategies/{listing_id}")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "live_metrics" not in attrs


class TestCategories:
    def test_list_categories(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(name="momentum", label="Momentum", description="Price momentum"),
            FakeRecord(name="breakout", label="Breakout", description="Range breakouts"),
        ]

        resp = tc.get("/strategies/categories")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2


# ===================================================================
# Subscriptions
# ===================================================================


class TestSubscribe:
    def test_subscribe_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        sub_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),
            FakeRecord(
                id=sub_id,
                listing_id=listing_id,
                user_id="user1",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/strategies/{listing_id}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["attributes"]["user_id"] == "user1"

    def test_subscribe_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 404

    def test_subscribe_duplicate(self, client):
        tc, conn = client
        import asyncpg

        listing_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),
            asyncpg.UniqueViolationError(""),
        ]

        resp = tc.post(
            f"/strategies/{listing_id}/subscribe",
            json={"user_id": "user1"},
        )
        assert resp.status_code == 409

    def test_unsubscribe_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=uuid.uuid4())

        resp = tc.delete(f"/strategies/{listing_id}/subscribe?user_id=user1")
        assert resp.status_code == 204

    def test_unsubscribe_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.delete(f"/strategies/{uuid.uuid4()}/subscribe?user_id=user1")
        assert resp.status_code == 404


# ===================================================================
# Ratings
# ===================================================================


class TestRatings:
    def test_rate_success(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        rating_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=listing_id),
            FakeRecord(
                id=rating_id,
                listing_id=listing_id,
                user_id="user1",
                score=5,
                review="Great!",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            f"/strategies/{listing_id}/rate",
            json={"user_id": "user1", "score": 5, "review": "Great!"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["attributes"]["score"] == 5

    def test_rate_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/rate",
            json={"user_id": "user1", "score": 3},
        )
        assert resp.status_code == 404

    def test_rate_invalid_score(self, client):
        tc, conn = client
        resp = tc.post(
            f"/strategies/{uuid.uuid4()}/rate",
            json={"user_id": "user1", "score": 6},
        )
        assert resp.status_code == 422

    def test_list_ratings(self, client):
        tc, conn = client
        listing_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=listing_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=uuid.uuid4(),
                listing_id=listing_id,
                user_id="user1",
                score=4,
                review="Good",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/strategies/{listing_id}/ratings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["data"][0]["attributes"]["score"] == 4


# ===================================================================
# Leaderboard
# ===================================================================


class TestLeaderboard:
    def test_get_leaderboard(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = [_fake_snapshot(strategy_id)]
        conn.fetchval.return_value = 1

        resp = tc.get("/leaderboard?period=monthly")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["total_return_pct"] == 42.5
        assert attrs["sharpe_ratio"] == 2.1
        assert attrs["rank"] == 1

    def test_get_leaderboard_with_category(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/leaderboard?period=weekly&category=momentum")
        assert resp.status_code == 200

    def test_get_leaderboard_sort_by_sharpe(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/leaderboard?sort_by=sharpe_ratio")
        assert resp.status_code == 200

    def test_get_leaderboard_cached(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetch.return_value = [_fake_snapshot(strategy_id)]
        conn.fetchval.return_value = 1

        # First call
        resp1 = tc.get("/leaderboard?period=daily")
        assert resp1.status_code == 200

        # Second call should hit cache (conn should only be called once)
        resp2 = tc.get("/leaderboard?period=daily")
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()

    def test_leaderboard_periods(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                period="monthly",
                latest_snapshot=date(2026, 3, 1),
                strategy_count=50,
            )
        ]

        resp = tc.get("/leaderboard/periods")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["attributes"]["period"] == "monthly"


# ===================================================================
# Comparison
# ===================================================================


class TestComparison:
    def test_compare_two_strategies(self, client):
        tc, conn = client
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        conn.fetch.side_effect = [
            [_fake_listing(id1, sid1), _fake_listing(id2, sid2)],
            [
                FakeRecord(
                    strategy_id=sid1,
                    total_return_pct=42.5,
                    sharpe_ratio=2.1,
                    win_rate=0.68,
                    max_drawdown_pct=-12.3,
                    trade_count=150,
                    consistency_score=0.85,
                    snapshot_date=date(2026, 3, 1),
                ),
                FakeRecord(
                    strategy_id=sid2,
                    total_return_pct=30.2,
                    sharpe_ratio=1.5,
                    win_rate=0.55,
                    max_drawdown_pct=-18.0,
                    trade_count=200,
                    consistency_score=0.72,
                    snapshot_date=date(2026, 3, 1),
                ),
            ],
        ]

        resp = tc.get(f"/compare?ids={id1},{id2}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert body["data"][0]["attributes"]["metrics"]["sharpe_ratio"] == 2.1
        assert body["data"][1]["attributes"]["metrics"]["sharpe_ratio"] == 1.5

    def test_compare_too_few(self, client):
        tc, conn = client
        resp = tc.get(f"/compare?ids={uuid.uuid4()}")
        assert resp.status_code == 422

    def test_compare_too_many(self, client):
        tc, conn = client
        ids = ",".join(str(uuid.uuid4()) for _ in range(6))
        resp = tc.get(f"/compare?ids={ids}")
        assert resp.status_code == 422

    def test_compare_not_found(self, client):
        tc, conn = client
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        conn.fetch.side_effect = [[], []]

        resp = tc.get(f"/compare?ids={id1},{id2}")
        assert resp.status_code == 404
