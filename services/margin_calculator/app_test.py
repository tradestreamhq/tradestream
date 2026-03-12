"""Tests for the Margin Calculator REST API."""

import pytest
from fastapi.testclient import TestClient

from services.margin_calculator.app import create_app
from services.margin_calculator.calculator import MarginCalculator
from services.margin_calculator.models import ExchangeMarginRates


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def custom_client():
    rates = {
        "testex": ExchangeMarginRates(
            exchange="testex",
            initial_rate=0.40,
            maintenance_rate=0.20,
            portfolio_rate=0.10,
        ),
        "default": ExchangeMarginRates(
            exchange="default",
            initial_rate=0.50,
            maintenance_rate=0.25,
            portfolio_rate=0.15,
        ),
    }
    calc = MarginCalculator(exchange_rates=rates)
    app = create_app(calculator=calc)
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ready(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200


class TestGetRequirements:
    def test_basic_buy(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 100000.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["notional_value"] == 60000.0
        assert attrs["initial_margin"] == 30000.0
        assert attrs["maintenance_margin"] == 15000.0
        assert attrs["can_execute"] is True

    def test_sell_order(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "ETH/USD",
                "qty": 10.0,
                "side": "SELL",
                "price": 3000.0,
                "account_equity": 50000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["side"] == "SELL"
        assert attrs["notional_value"] == 30000.0

    def test_insufficient_margin(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 2.0,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 50000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["can_execute"] is False
        assert "Insufficient margin" in attrs["reason"]

    def test_existing_margin_used(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 100000.0,
                "existing_margin_used": 80000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["margin_available"] == 20000.0
        assert attrs["can_execute"] is False

    def test_invalid_side(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "HOLD",
                "price": 60000.0,
                "account_equity": 100000.0,
            },
        )
        assert resp.status_code == 422

    def test_case_insensitive_side(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "buy",
                "price": 60000.0,
                "account_equity": 100000.0,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["side"] == "BUY"


class TestPostRequirements:
    def test_post_body(self, client):
        resp = client.post(
            "/requirements",
            json={
                "symbol": "BTC/USD",
                "quantity": 0.5,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 100000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["notional_value"] == 30000.0
        assert attrs["initial_margin"] == 15000.0


class TestExchangeRates:
    def test_list_exchanges(self, client):
        resp = client.get("/exchanges")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "coinbase" in attrs
        assert "binance" in attrs
        assert "default" in attrs

    def test_custom_exchange(self, custom_client):
        resp = custom_client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "BUY",
                "price": 60000.0,
                "exchange": "testex",
                "account_equity": 100000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # testex initial_rate = 0.40, so 60000 * 0.40 = 24000
        assert attrs["initial_margin"] == 24000.0
        assert attrs["maintenance_margin"] == 12000.0
        assert attrs["portfolio_margin"] == 6000.0


class TestMarginUtilization:
    def test_utilization_calculation(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 100000.0,
                "existing_margin_used": 20000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # utilization = (20000 + 30000) / 100000 * 100 = 50%
        assert attrs["margin_utilization_pct"] == 50.0

    def test_buying_power(self, client):
        resp = client.get(
            "/requirements",
            params={
                "symbol": "BTC/USD",
                "qty": 1.0,
                "side": "BUY",
                "price": 60000.0,
                "account_equity": 100000.0,
                "existing_margin_used": 20000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # buying_power = (100000 - 20000) / 0.50 = 160000
        assert attrs["buying_power"] == 160000.0
