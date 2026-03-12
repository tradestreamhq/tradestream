"""Tests for the Liquidity Scoring REST API and scoring engine."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.liquidity_scoring.app import create_app
from services.liquidity_scoring.models import (
    LiquidityCategory,
    LiquidityMetrics,
    LiquidityScore,
)
from services.liquidity_scoring.scorer import (
    _log_normalize,
    _spread_score,
    compute_score,
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


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# --- Scorer unit tests ---


class TestLogNormalize:
    def test_zero_value(self):
        assert _log_normalize(0, 1000) == 0.0

    def test_negative_value(self):
        assert _log_normalize(-5, 1000) == 0.0

    def test_at_reference(self):
        assert _log_normalize(1000, 1000) == 100.0

    def test_above_reference(self):
        assert _log_normalize(5000, 1000) == 100.0

    def test_one_order_below(self):
        # 100/1000 = 0.1 => log10(0.1) = -1 => ((-1)+3)/3*100 = 66.67
        score = _log_normalize(100, 1000)
        assert 66 <= score <= 67

    def test_two_orders_below(self):
        # 10/1000 = 0.01 => log10(0.01) = -2 => ((-2)+3)/3*100 = 33.33
        score = _log_normalize(10, 1000)
        assert 33 <= score <= 34

    def test_three_orders_below(self):
        # 1/1000 = 0.001 => log10 = -3 => clamped => 0
        score = _log_normalize(1, 1000)
        assert score == 0.0


class TestSpreadScore:
    def test_zero_spread(self):
        assert _spread_score(0) == 100.0

    def test_at_reference(self):
        assert _spread_score(0.01) == 100.0

    def test_below_reference(self):
        assert _spread_score(0.005) == 100.0

    def test_wide_spread(self):
        # 0.01/0.1 = 0.1 => log10(0.1) = -1 => ((-1)+3)/3*100 = 66.67
        score = _spread_score(0.1)
        assert 66 <= score <= 67

    def test_very_wide_spread(self):
        score = _spread_score(100.0)
        assert score == 0.0


class TestComputeScore:
    def test_perfect_metrics(self):
        metrics = LiquidityMetrics(
            symbol="BTC/USD",
            avg_daily_volume_30d=2_000_000_000,
            avg_spread_pct=0.005,
            order_book_depth_usd=20_000_000,
            trade_frequency_per_hour=10000,
        )
        total, vol, spread, depth, freq = compute_score(metrics)
        assert total == 100.0
        assert vol == 100.0
        assert spread == 100.0
        assert depth == 100.0
        assert freq == 100.0

    def test_zero_metrics(self):
        metrics = LiquidityMetrics(
            symbol="DEAD/USD",
            avg_daily_volume_30d=0,
            avg_spread_pct=100,
            order_book_depth_usd=0,
            trade_frequency_per_hour=0,
        )
        total, vol, spread, depth, freq = compute_score(metrics)
        assert total == 0.0

    def test_mid_range_metrics(self):
        metrics = LiquidityMetrics(
            symbol="MID/USD",
            avg_daily_volume_30d=10_000_000,
            avg_spread_pct=0.1,
            order_book_depth_usd=100_000,
            trade_frequency_per_hour=50,
        )
        total, vol, spread, depth, freq = compute_score(metrics)
        assert 0 < total < 100
        assert 0 < vol < 100


# --- Model tests ---


class TestLiquidityScoreModel:
    def test_categorize_high(self):
        assert LiquidityScore.categorize(80) == LiquidityCategory.HIGH
        assert LiquidityScore.categorize(100) == LiquidityCategory.HIGH

    def test_categorize_medium(self):
        assert LiquidityScore.categorize(40) == LiquidityCategory.MEDIUM
        assert LiquidityScore.categorize(79.9) == LiquidityCategory.MEDIUM

    def test_categorize_low(self):
        assert LiquidityScore.categorize(0) == LiquidityCategory.LOW
        assert LiquidityScore.categorize(39.9) == LiquidityCategory.LOW


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestGetLiquidityScore:
    def test_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            symbol="BTC/USD",
            score=85.5,
            category="high",
            volume_component=90.0,
            spread_component=80.0,
            depth_component=85.0,
            frequency_component=75.0,
            scored_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        resp = tc.get("/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["score"] == 85.5
        assert attrs["category"] == "high"

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get("/UNKNOWN%2FUSD")
        assert resp.status_code == 404


class TestGetLiquidityHistory:
    def test_returns_history(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                score=85.5,
                category="high",
                scored_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            FakeRecord(
                symbol="BTC/USD",
                score=82.0,
                category="high",
                scored_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchval.return_value = 2
        resp = tc.get("/BTC%2FUSD/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] == 2


class TestListLiquidityScores:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                score=85.5,
                category="high",
                volume_component=90.0,
                spread_component=80.0,
                depth_component=85.0,
                frequency_component=75.0,
                scored_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchval.return_value = 1
        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_filter_by_category(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0
        resp = tc.get("/?category=high")
        assert resp.status_code == 200

    def test_invalid_category(self, client):
        tc, conn = client
        resp = tc.get("/?category=invalid")
        assert resp.status_code == 422


class TestScoreAsset:
    def test_score_and_store(self, client):
        tc, conn = client
        conn.fetchval.return_value = "550e8400-e29b-41d4-a716-446655440000"
        resp = tc.post(
            "/score",
            json={
                "symbol": "BTC/USD",
                "avg_daily_volume_30d": 500_000_000,
                "avg_spread_pct": 0.02,
                "order_book_depth_usd": 5_000_000,
                "trade_frequency_per_hour": 3000,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert 0 <= attrs["score"] <= 100
        assert attrs["category"] in ("high", "medium", "low")
        assert attrs["symbol"] == "BTC/USD"
