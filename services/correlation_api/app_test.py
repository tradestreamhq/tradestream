"""Tests for the Correlation Analysis REST API."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.correlation_api.app import (
    _compute_correlation_matrix,
    _detect_regime_changes,
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


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# ---- Unit tests for pure computation ----


class TestComputeCorrelationMatrix:
    def test_perfectly_correlated(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, 0.0],
            "B": [0.01, 0.02, -0.01, 0.03, 0.0],
        }
        matrix = _compute_correlation_matrix(returns)
        assert matrix["A"]["A"] == pytest.approx(1.0, abs=1e-4)
        assert matrix["A"]["B"] == pytest.approx(1.0, abs=1e-4)
        assert matrix["B"]["A"] == pytest.approx(1.0, abs=1e-4)

    def test_inversely_correlated(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03],
            "B": [-0.01, -0.02, 0.01, -0.03],
        }
        matrix = _compute_correlation_matrix(returns)
        assert matrix["A"]["B"] == pytest.approx(-1.0, abs=1e-4)

    def test_uncorrelated_synthetic(self):
        np.random.seed(42)
        n = 500
        returns = {
            "X": list(np.random.randn(n) * 0.01),
            "Y": list(np.random.randn(n) * 0.01),
        }
        matrix = _compute_correlation_matrix(returns)
        # With independent random series, correlation should be near zero
        assert abs(matrix["X"]["Y"]) < 0.15

    def test_empty_returns(self):
        matrix = _compute_correlation_matrix({})
        assert matrix == {}

    def test_single_strategy(self):
        returns = {"A": [0.01, 0.02, -0.01]}
        matrix = _compute_correlation_matrix(returns)
        assert matrix["A"]["A"] == pytest.approx(1.0, abs=1e-4)

    def test_constant_series_no_nan(self):
        returns = {
            "A": [0.01, 0.01, 0.01],
            "B": [0.02, 0.03, 0.04],
        }
        matrix = _compute_correlation_matrix(returns)
        # Constant series should yield 0 correlation (NaN replaced)
        assert matrix["A"]["B"] == pytest.approx(0.0, abs=1e-4)

    def test_three_strategies(self):
        np.random.seed(123)
        base = np.random.randn(100) * 0.01
        returns = {
            "A": list(base),
            "B": list(base + np.random.randn(100) * 0.001),
            "C": list(-base),
        }
        matrix = _compute_correlation_matrix(returns)
        # A and B should be highly correlated
        assert matrix["A"]["B"] > 0.9
        # A and C should be negatively correlated
        assert matrix["A"]["C"] < -0.9


class TestDetectRegimeChanges:
    def test_no_change(self):
        current = {"A": {"A": 1.0, "B": 0.5}, "B": {"A": 0.5, "B": 1.0}}
        previous = {"A": {"A": 1.0, "B": 0.5}, "B": {"A": 0.5, "B": 1.0}}
        alerts = _detect_regime_changes(current, previous)
        assert alerts == []

    def test_significant_change(self):
        current = {"A": {"A": 1.0, "B": 0.8}, "B": {"A": 0.8, "B": 1.0}}
        previous = {"A": {"A": 1.0, "B": 0.3}, "B": {"A": 0.3, "B": 1.0}}
        alerts = _detect_regime_changes(current, previous)
        assert len(alerts) == 1
        assert alerts[0]["absolute_change"] == pytest.approx(0.5, abs=1e-4)

    def test_below_threshold(self):
        current = {"A": {"A": 1.0, "B": 0.5}, "B": {"A": 0.5, "B": 1.0}}
        previous = {"A": {"A": 1.0, "B": 0.4}, "B": {"A": 0.4, "B": 1.0}}
        alerts = _detect_regime_changes(current, previous, threshold=0.3)
        assert alerts == []

    def test_custom_threshold(self):
        current = {"A": {"A": 1.0, "B": 0.5}, "B": {"A": 0.5, "B": 1.0}}
        previous = {"A": {"A": 1.0, "B": 0.4}, "B": {"A": 0.4, "B": 1.0}}
        alerts = _detect_regime_changes(current, previous, threshold=0.1)
        assert len(alerts) == 1

    def test_no_duplicate_alerts(self):
        """Each pair should only appear once."""
        current = {
            "A": {"A": 1.0, "B": 0.9, "C": 0.1},
            "B": {"A": 0.9, "B": 1.0, "C": 0.2},
            "C": {"A": 0.1, "B": 0.2, "C": 1.0},
        }
        previous = {
            "A": {"A": 1.0, "B": 0.2, "C": 0.1},
            "B": {"A": 0.2, "B": 1.0, "C": 0.2},
            "C": {"A": 0.1, "B": 0.2, "C": 1.0},
        }
        alerts = _detect_regime_changes(current, previous)
        # Only A-B should trigger (change of 0.7)
        assert len(alerts) == 1
        assert set(alerts[0]["pair"]) == {"A", "B"}


# ---- API endpoint tests ----


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestStrategyCorrelations:
    def test_valid_window(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(strategy_id="s1", metric_date="2026-01-01", daily_return=0.01),
            FakeRecord(strategy_id="s1", metric_date="2026-01-02", daily_return=0.02),
            FakeRecord(strategy_id="s2", metric_date="2026-01-01", daily_return=-0.01),
            FakeRecord(strategy_id="s2", metric_date="2026-01-02", daily_return=-0.02),
        ]
        conn.fetchrow.return_value = None  # no previous snapshot

        resp = tc.get("/strategies?window=60")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "matrix" in attrs
        assert "s1" in attrs["matrix"]
        assert attrs["window"] == 60

    def test_invalid_window(self, client):
        tc, conn = client
        resp = tc.get("/strategies?window=45")
        assert resp.status_code == 422

    def test_empty_returns(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchrow.return_value = None

        resp = tc.get("/strategies?window=30")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["matrix"] == {}


class TestAssetCorrelations:
    def test_valid_request(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(symbol="BTC/USD", metric_date="2026-01-01", daily_return=0.03),
            FakeRecord(symbol="BTC/USD", metric_date="2026-01-02", daily_return=0.01),
            FakeRecord(symbol="ETH/USD", metric_date="2026-01-01", daily_return=0.025),
            FakeRecord(symbol="ETH/USD", metric_date="2026-01-02", daily_return=0.015),
        ]
        conn.fetchrow.return_value = None

        resp = tc.get("/assets?window=90")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "BTC/USD" in attrs["matrix"]
        assert "ETH/USD" in attrs["matrix"]

    def test_invalid_window(self, client):
        tc, conn = client
        resp = tc.get("/assets?window=15")
        assert resp.status_code == 422


class TestCorrelationAlerts:
    def test_get_alerts(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id="abc-123",
                correlation_type="strategy",
                pair_a="s1",
                pair_b="s2",
                previous_correlation=0.2,
                current_correlation=0.8,
                absolute_change=0.6,
                detected_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["absolute_change"] == 0.6

    def test_alerts_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/alerts?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0
