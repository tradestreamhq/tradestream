"""Tests for Prediction Reasoning API endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.prediction_reasoning.app import create_app


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


def _sample_reasoning_row():
    return FakeRecord(
        id="reas-1",
        signal_id="sig-1",
        strategy_name="RSI_REVERSAL",
        symbol="ETH/USD",
        signal_type="BUY",
        contributing_factors=[
            {
                "indicator_name": "RSI(14)",
                "value": 32.5,
                "threshold": 30.0,
                "condition": "crossed_above",
                "weight": 0.4,
                "description": "RSI(14) crossed above 30",
            }
        ],
        indicator_values={"RSI_14": 32.5},
        market_context={
            "trend_direction": "bullish",
            "trend_strength": 0.6,
            "volatility_percentile": 0.5,
            "volume_ratio": 1.8,
            "market_regime": "trending",
            "sentiment": "neutral",
        },
        confidence_breakdown={
            "indicator_agreement": 0.85,
            "volume_confirmation": 0.75,
            "trend_alignment": 0.70,
            "volatility_context": 0.60,
            "overall_confidence": 0.76,
            "quality_grade": "B",
        },
        explanation_text="BUY signal triggered because RSI(14) crossed above 30",
        historical_context="This pattern has resulted in profitable trades 67% of the time",
        risk_factors=[],
        validation_level="validated",
        expected_return=3.2,
        expected_return_ci_lower=1.7,
        expected_return_ci_upper=4.7,
        predicted_timeframe_hours=24,
        created_at=None,
    )


class TestGetSignalReasoning:
    def test_returns_reasoning_for_signal(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = _sample_reasoning_row()
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/signals/sig-1/reasoning")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "signal_reasoning"
        attrs = body["data"]["attributes"]
        assert attrs["strategy_name"] == "RSI_REVERSAL"
        assert attrs["explanation_text"].startswith("BUY signal triggered")
        assert attrs["expected_return"] == 3.2

    def test_returns_404_when_not_found(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/signals/nonexistent/reasoning")
        assert resp.status_code == 404


class TestGetReasoningById:
    def test_returns_reasoning(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = _sample_reasoning_row()
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/reasoning/reas-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "reas-1"

    def test_returns_404_for_missing(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/reasoning/missing")
        assert resp.status_code == 404


class TestListReasoning:
    def test_returns_empty_list(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/reasoning")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_returns_filtered_list(self):
        pool, conn = _make_pool()
        row = _sample_reasoning_row()
        conn.fetch.return_value = [row]
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/reasoning?strategy=RSI_REVERSAL&symbol=ETH/USD")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["attributes"]["strategy_name"] == "RSI_REVERSAL"

    def test_respects_pagination(self):
        pool, conn = _make_pool()
        conn.fetch.return_value = []
        app = create_app(pool)
        client = TestClient(app)

        resp = client.get("/reasoning?limit=10&offset=5")
        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert meta["limit"] == 10
        assert meta["offset"] == 5
