"""Tests for Signal Quality API endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.signal_quality.app import create_app


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


class TestQualityScoresEndpoint:
    def test_get_scores_empty(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/scores")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_get_scores_with_data(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = [
            FakeRecord(
                id="score-1", signal_id="sig-1", strategy_name="MACD_CROSSOVER",
                symbol="BTC/USD", confidence=0.82, indicator_agreement=0.9,
                volume_confirmation=0.7, trend_alignment=0.85,
                volatility_context=0.6, quality_grade="A", created_at=None,
            ),
        ]
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/scores?strategy=MACD_CROSSOVER")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["attributes"]["quality_grade"] == "A"


class TestDashboardEndpoint:
    def test_dashboard_returns_structure(self):
        pool, conn = _make_pool()
        # rankings
        conn.fetch.side_effect = [
            [],  # rankings
            [],  # recent outcomes
            [],  # grade distribution
        ]
        conn.fetchrow.return_value = FakeRecord(
            total_signals=0, total_wins=0, total_losses=0,
            overall_win_rate=None, avg_return=None,
        )
        conn.fetchval.return_value = 1  # health check

        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "overall" in attrs
        assert "strategy_rankings" in attrs
        assert "recent_outcomes" in attrs
        assert "grade_distribution" in attrs
