"""Tests for the Position Sizing Engine REST API."""

import pytest
from fastapi.testclient import TestClient

from services.position_sizing_engine.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_ready(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200


class TestListMethods:
    def test_returns_all_methods(self, client):
        resp = client.get("/methods")
        assert resp.status_code == 200
        body = resp.json()
        methods = body["data"]
        assert len(methods) == 4
        ids = {m["attributes"]["id"] for m in methods}
        assert "fixed_fractional" in ids
        assert "kelly_criterion" in ids
        assert "volatility_adjusted" in ids
        assert "equal_weight" in ids

    def test_methods_have_descriptions(self, client):
        resp = client.get("/methods")
        body = resp.json()
        for m in body["data"]:
            assert "description" in m["attributes"]
            assert len(m["attributes"]["description"]) > 0


class TestCalculateFixedFractional:
    def test_basic(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-1",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "current_equity": 100000.0,
                "method": "fixed_fractional",
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["shares"] == pytest.approx(400.0)
        assert attrs["dollar_amount"] == pytest.approx(40000.0)
        assert attrs["risk_amount"] == pytest.approx(2000.0)

    def test_missing_stop_loss_returns_422(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-1",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "current_equity": 100000.0,
                "method": "fixed_fractional",
            },
        )
        assert resp.status_code == 422

    def test_zero_equity_rejected(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-1",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "current_equity": 0.0,
                "method": "fixed_fractional",
            },
        )
        # Pydantic rejects current_equity <= 0
        assert resp.status_code == 422


class TestCalculateKelly:
    def test_basic(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-2",
                "signal_strength": 1.0,
                "entry_price": 50.0,
                "current_equity": 50000.0,
                "method": "kelly_criterion",
                "win_rate": 0.6,
                "payoff_ratio": 1.5,
                "kelly_fraction": 0.5,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["shares"] > 0
        assert attrs["method"] == "kelly_criterion"


class TestCalculateVolatilityAdjusted:
    def test_basic(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-3",
                "signal_strength": 0.8,
                "entry_price": 200.0,
                "current_equity": 100000.0,
                "method": "volatility_adjusted",
                "atr": 5.0,
                "atr_multiplier": 2.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["shares"] > 0

    def test_missing_atr_returns_422(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-3",
                "signal_strength": 1.0,
                "entry_price": 200.0,
                "current_equity": 100000.0,
                "method": "volatility_adjusted",
            },
        )
        assert resp.status_code == 422


class TestCalculateEqualWeight:
    def test_basic(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-4",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "current_equity": 100000.0,
                "method": "equal_weight",
                "num_positions": 10,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["shares"] == pytest.approx(100.0)
        assert attrs["dollar_amount"] == pytest.approx(10000.0)


class TestPortfolioConstraints:
    def test_constrained_by_exposure(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-5",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "current_equity": 100000.0,
                "method": "fixed_fractional",
                "current_exposure": 95000.0,
                "max_total_exposure_pct": 1.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["dollar_amount"] <= 5000.01
        assert attrs["constrained"] is True

    def test_response_envelope(self, client):
        resp = client.post(
            "/calculate",
            json={
                "strategy_id": "strat-1",
                "signal_strength": 1.0,
                "entry_price": 100.0,
                "stop_loss_price": 95.0,
                "current_equity": 100000.0,
            },
        )
        body = resp.json()
        assert "data" in body
        assert body["data"]["type"] == "position_size"
        assert body["data"]["id"] == "strat-1"
        assert "attributes" in body["data"]
