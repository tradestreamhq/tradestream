"""Tests for the Correlation Matrix REST API."""

import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.correlation_matrix.app import create_app
from services.correlation_matrix.calculator import (
    build_correlation_matrix,
    compute_pairwise_correlation,
    compute_returns,
    detect_breakdowns,
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


# --- Calculator unit tests ---


class TestComputeReturns:
    def test_basic_returns(self):
        prices = [100.0, 110.0, 105.0, 115.0]
        returns = compute_returns(prices)
        assert len(returns) == 3
        assert abs(returns[0] - math.log(110.0 / 100.0)) < 1e-10

    def test_single_price(self):
        returns = compute_returns([100.0])
        assert len(returns) == 0

    def test_empty_prices(self):
        returns = compute_returns([])
        assert len(returns) == 0


class TestComputePairwiseCorrelation:
    def test_perfect_positive(self):
        import numpy as np

        a = np.array([0.01, 0.02, -0.01, 0.03, 0.01, -0.02])
        corr = compute_pairwise_correlation(a, a)
        assert corr is not None
        assert abs(corr - 1.0) < 1e-6

    def test_perfect_negative(self):
        import numpy as np

        a = np.array([0.01, 0.02, -0.01, 0.03, 0.01, -0.02])
        b = -a
        corr = compute_pairwise_correlation(a, b)
        assert corr is not None
        assert abs(corr - (-1.0)) < 1e-6

    def test_insufficient_data(self):
        import numpy as np

        a = np.array([0.01, 0.02])
        b = np.array([0.03, 0.01])
        corr = compute_pairwise_correlation(a, b)
        assert corr is None

    def test_zero_variance(self):
        import numpy as np

        a = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        b = np.array([0.02, 0.03, 0.01, 0.04, 0.02])
        corr = compute_pairwise_correlation(a, b)
        assert corr is None


class TestBuildCorrelationMatrix:
    def test_diagonal_is_one(self):
        symbols = ["BTC", "ETH"]
        prices = {
            "BTC": [100, 102, 101, 103, 104, 105, 106],
            "ETH": [50, 51, 49, 52, 53, 51, 54],
        }
        matrix = build_correlation_matrix(symbols, prices, 5)
        assert matrix["BTC"]["BTC"] == 1.0
        assert matrix["ETH"]["ETH"] == 1.0

    def test_symmetry(self):
        symbols = ["BTC", "ETH", "SOL"]
        prices = {
            "BTC": [100, 102, 101, 103, 104, 105, 106, 108],
            "ETH": [50, 51, 49, 52, 53, 51, 54, 55],
            "SOL": [10, 11, 9, 12, 11, 13, 14, 12],
        }
        matrix = build_correlation_matrix(symbols, prices, 6)
        assert matrix["BTC"]["ETH"] == matrix["ETH"]["BTC"]
        assert matrix["BTC"]["SOL"] == matrix["SOL"]["BTC"]
        assert matrix["ETH"]["SOL"] == matrix["SOL"]["ETH"]

    def test_missing_symbol_data(self):
        symbols = ["BTC", "ETH"]
        prices = {"BTC": [100, 102, 103], "ETH": []}
        matrix = build_correlation_matrix(symbols, prices, 5)
        assert matrix["BTC"]["ETH"] is None


class TestDetectBreakdowns:
    def test_detects_large_change(self):
        current = {"BTC": {"ETH": 0.9}, "ETH": {"BTC": 0.9}}
        historical = {"BTC": {"ETH": 0.3}, "ETH": {"BTC": 0.3}}
        breakdowns = detect_breakdowns(
            current, historical, ["BTC", "ETH"], "30d", threshold=0.3
        )
        assert len(breakdowns) == 1
        assert breakdowns[0]["symbol_a"] == "BTC"
        assert breakdowns[0]["symbol_b"] == "ETH"
        assert abs(breakdowns[0]["change"] - 0.6) < 1e-6

    def test_no_breakdown_below_threshold(self):
        current = {"BTC": {"ETH": 0.5}, "ETH": {"BTC": 0.5}}
        historical = {"BTC": {"ETH": 0.45}, "ETH": {"BTC": 0.45}}
        breakdowns = detect_breakdowns(
            current, historical, ["BTC", "ETH"], "30d", threshold=0.3
        )
        assert len(breakdowns) == 0

    def test_skips_none_values(self):
        current = {"BTC": {"ETH": None}, "ETH": {"BTC": None}}
        historical = {"BTC": {"ETH": 0.5}, "ETH": {"BTC": 0.5}}
        breakdowns = detect_breakdowns(current, historical, ["BTC", "ETH"], "30d")
        assert len(breakdowns) == 0


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestCorrelationsEndpoint:
    def test_get_pair_correlation(self, client):
        tc, conn = client
        # Mock price data: return rows for BTC and ETH
        conn.fetch.return_value = [
            FakeRecord(symbol="BTC", close=100.0, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ] + [
            FakeRecord(symbol="ETH", close=50.0 + i, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ]

        resp = tc.get("/correlations?symbol_a=BTC&symbol_b=ETH&window=30d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "correlation_pair"
        attrs = body["data"]["attributes"]
        assert attrs["symbol_a"] == "BTC"
        assert attrs["symbol_b"] == "ETH"
        assert "correlation" in attrs

    def test_get_matrix(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(symbol="BTC", close=100.0 + i, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ] + [
            FakeRecord(symbol="ETH", close=50.0 + i * 0.5, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ]

        resp = tc.get("/correlations?symbols=BTC,ETH&window=30d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "correlation_matrix"
        attrs = body["data"]["attributes"]
        assert "BTC" in attrs["matrix"]
        assert "ETH" in attrs["matrix"]

    def test_insufficient_symbols(self, client):
        tc, conn = client
        resp = tc.get("/correlations?symbols=BTC&window=30d")
        assert resp.status_code == 422

    def test_default_symbols_from_candles(self, client):
        tc, conn = client
        # First call returns distinct symbols, second returns price data
        conn.fetch.side_effect = [
            [FakeRecord(symbol="BTC"), FakeRecord(symbol="ETH")],
            [
                FakeRecord(symbol="BTC", close=100.0 + i, bucket=datetime(2026, 1, i))
                for i in range(1, 10)
            ]
            + [
                FakeRecord(symbol="ETH", close=50.0 + i, bucket=datetime(2026, 1, i))
                for i in range(1, 10)
            ],
        ]

        resp = tc.get("/correlations?window=30d")
        assert resp.status_code == 200


class TestBreakdownsEndpoint:
    def test_get_breakdowns(self, client):
        tc, conn = client
        # Two fetch calls for current and historical prices
        price_rows = [
            FakeRecord(symbol="BTC", close=100.0 + i, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ] + [
            FakeRecord(symbol="ETH", close=50.0 + i, bucket=datetime(2026, 1, i))
            for i in range(1, 10)
        ]
        conn.fetch.return_value = price_rows

        resp = tc.get("/correlations/breakdowns?symbols=BTC,ETH&window=30d")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body

    def test_breakdowns_insufficient_symbols(self, client):
        tc, conn = client
        resp = tc.get("/correlations/breakdowns?symbols=BTC&window=30d")
        assert resp.status_code == 422
