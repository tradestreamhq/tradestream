"""Tests for the Order Execution Simulator REST API."""

import pytest
from fastapi.testclient import TestClient

from services.order_simulator.app import create_app
from services.order_simulator.models import FeeSchedule, SlippageConfig, SlippageModel


@pytest.fixture
def client():
    config = SlippageConfig(model=SlippageModel.FIXED, value=0.0)
    fee_sched = FeeSchedule(maker_fee=0.0, taker_fee=0.0)
    app = create_app(
        initial_balance=100_000.0,
        slippage_config=config,
        fee_schedule=fee_sched,
    )
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestPlaceOrderEndpoint:
    def test_place_market_order(self, client):
        resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "simulated_order"
        assert body["data"]["attributes"]["status"] == "OPEN"

    def test_place_limit_order(self, client):
        resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "LIMIT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 50000.0,
        })
        assert resp.status_code == 201

    def test_limit_order_without_price_rejected(self, client):
        resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "LIMIT",
            "side": "BUY",
            "quantity": 0.1,
        })
        assert resp.status_code == 422

    def test_invalid_quantity(self, client):
        resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": -1,
        })
        assert resp.status_code == 422


class TestListOrdersEndpoint:
    def test_list_empty(self, client):
        resp = client.get("/orders")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_with_orders(self, client):
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        resp = client.get("/orders")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_filter_by_instrument(self, client):
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        client.post("/orders", json={
            "instrument": "ETH/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 1.0,
        })
        resp = client.get("/orders?instrument=BTC/USD")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestGetOrderEndpoint:
    def test_get_existing_order(self, client):
        create_resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        order_id = create_resp.json()["data"]["id"]
        resp = client.get(f"/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == order_id

    def test_get_nonexistent_order(self, client):
        resp = client.get("/orders/nonexistent")
        assert resp.status_code == 404


class TestCancelOrderEndpoint:
    def test_cancel_open_order(self, client):
        create_resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        order_id = create_resp.json()["data"]["id"]
        resp = client.delete(f"/orders/{order_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["status"] == "CANCELLED"

    def test_cancel_nonexistent(self, client):
        resp = client.delete("/orders/nonexistent")
        assert resp.status_code == 404

    def test_cancel_already_cancelled(self, client):
        create_resp = client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        order_id = create_resp.json()["data"]["id"]
        client.delete(f"/orders/{order_id}")
        resp = client.delete(f"/orders/{order_id}")
        assert resp.status_code == 422


class TestBalanceEndpoint:
    def test_get_initial_balance(self, client):
        resp = client.get("/balance")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["cash_balance"] == 100_000.0
        assert attrs["initial_balance"] == 100_000.0

    def test_balance_after_buy(self, client):
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 1.0,
        })
        client.post("/tick", json={
            "instrument": "BTC/USD",
            "bid": 50000.0,
            "ask": 50000.0,
        })
        resp = client.get("/balance")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["cash_balance"] == pytest.approx(50_000.0, abs=0.01)
        assert "BTC/USD" in attrs["positions"]


class TestTickEndpoint:
    def test_process_tick_fills_order(self, client):
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 0.1,
        })
        resp = client.post("/tick", json={
            "instrument": "BTC/USD",
            "bid": 50000.0,
            "ask": 50000.0,
        })
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_tick_no_matching_orders(self, client):
        resp = client.post("/tick", json={
            "instrument": "BTC/USD",
            "bid": 50000.0,
            "ask": 50000.0,
        })
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestEndToEndFlow:
    def test_buy_then_sell_profit(self, client):
        # Place buy
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "BUY",
            "quantity": 1.0,
        })
        client.post("/tick", json={
            "instrument": "BTC/USD",
            "bid": 50000.0,
            "ask": 50000.0,
        })

        # Place sell at higher price
        client.post("/orders", json={
            "instrument": "BTC/USD",
            "order_type": "MARKET",
            "side": "SELL",
            "quantity": 1.0,
        })
        client.post("/tick", json={
            "instrument": "BTC/USD",
            "bid": 55000.0,
            "ask": 55000.0,
        })

        resp = client.get("/balance")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["cash_balance"] == pytest.approx(105_000.0, abs=0.01)
        assert attrs["positions"] == {}

    def test_limit_order_workflow(self, client):
        # Place limit buy below market
        create_resp = client.post("/orders", json={
            "instrument": "ETH/USD",
            "order_type": "LIMIT",
            "side": "BUY",
            "quantity": 10.0,
            "price": 3000.0,
        })
        order_id = create_resp.json()["data"]["id"]

        # Tick at higher price — no fill
        client.post("/tick", json={
            "instrument": "ETH/USD",
            "bid": 3100.0,
            "ask": 3110.0,
        })
        resp = client.get(f"/orders/{order_id}")
        assert resp.json()["data"]["attributes"]["status"] == "OPEN"

        # Tick at limit price — fill
        client.post("/tick", json={
            "instrument": "ETH/USD",
            "bid": 2990.0,
            "ask": 3000.0,
        })
        resp = client.get(f"/orders/{order_id}")
        assert resp.json()["data"]["attributes"]["status"] == "FILLED"
