"""Tests for the Correlation Engine REST API."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from services.correlation_engine.app import create_app


def _make_price_data(n=200, seed=42):
    """Generate deterministic price data for testing."""
    np.random.seed(seed)
    common = np.cumsum(np.random.randn(n))
    return {
        "BTC/USD": [
            {"close": float(common[i] + 50000 + np.random.randn() * 10), "time": f"2026-01-{i+1:03d}"}
            for i in range(n)
        ],
        "ETH/USD": [
            {"close": float(0.7 * common[i] + 3000 + np.random.randn() * 5), "time": f"2026-01-{i+1:03d}"}
            for i in range(n)
        ],
        "SOL/USD": [
            {"close": float(np.cumsum(np.random.randn(1))[0] + 100 + i * 0.1), "time": f"2026-01-{i+1:03d}"}
            for i in range(n)
        ],
    }


@pytest.fixture
def client():
    provider = MagicMock()
    price_data = _make_price_data()
    provider.get_symbols.return_value = list(price_data.keys())
    provider.get_prices.side_effect = lambda sym, limit=200: price_data.get(sym, [])[:limit]
    app = create_app(provider)
    return TestClient(app, raise_server_exceptions=False), provider


class TestHealthEndpoints:
    def test_health(self, client):
        tc, provider = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestCorrelationMatrix:
    def test_matrix_all_symbols(self, client):
        tc, provider = client
        resp = tc.get("/matrix")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "symbols" in attrs
        assert "matrix" in attrs
        assert len(attrs["symbols"]) == 3
        # Matrix should be 3x3
        assert len(attrs["matrix"]) == 3
        assert len(attrs["matrix"][0]) == 3
        # Diagonal should be 1.0
        for i in range(3):
            assert abs(attrs["matrix"][i][i] - 1.0) < 1e-10

    def test_matrix_specific_symbols(self, client):
        tc, provider = client
        resp = tc.get("/matrix?symbols=BTC/USD,ETH/USD")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["symbols"]) == 2

    def test_matrix_single_symbol_error(self, client):
        tc, provider = client
        resp = tc.get("/matrix?symbols=BTC/USD")
        assert resp.status_code == 422
        assert "2 symbols" in resp.json()["error"]["message"]


class TestPairwiseCorrelation:
    def test_pairwise(self, client):
        tc, provider = client
        resp = tc.get("/BTC%2FUSD/ETH%2FUSD?window=30")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "correlation" in attrs
        assert "cointegrated" in attrs
        assert "hedge_ratio" in attrs
        assert "rolling_correlation" in attrs
        assert "current_zscore" in attrs
        assert attrs["window"] == 30

    def test_pairwise_not_found(self, client):
        tc, provider = client
        provider.get_prices.side_effect = lambda sym, limit=200: []
        resp = tc.get("/FAKE1/FAKE2")
        assert resp.status_code == 404


class TestCointegratedPairs:
    def test_cointegrated_pairs(self, client):
        tc, provider = client
        resp = tc.get("/pairs/cointegrated")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        # All returned pairs should have p_value < 0.05
        for item in body["data"]:
            assert item["attributes"]["p_value"] < 0.05

    def test_cointegrated_pairs_with_symbols(self, client):
        tc, provider = client
        resp = tc.get("/pairs/cointegrated?symbols=BTC/USD,ETH/USD")
        assert resp.status_code == 200

    def test_cointegrated_single_symbol_error(self, client):
        tc, provider = client
        resp = tc.get("/pairs/cointegrated?symbols=BTC/USD")
        assert resp.status_code == 422
