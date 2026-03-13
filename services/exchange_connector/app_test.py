"""Tests for the Exchange Connector API and connectors."""

import pytest
from fastapi.testclient import TestClient

from services.exchange_connector.app import create_app
from services.exchange_connector.base import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from services.exchange_connector.mock_connector import MockExchangeConnector
from services.exchange_connector.registry import ExchangeRegistry


@pytest.fixture
def mock_connector():
    return MockExchangeConnector()


@pytest.fixture
def registry(mock_connector):
    reg = ExchangeRegistry()
    reg.register(mock_connector)
    return reg


@pytest.fixture
def client(registry):
    app = create_app(registry)
    return TestClient(app, raise_server_exceptions=False)


class TestMockConnector:
    def test_name(self, mock_connector):
        assert mock_connector.name == "mock"

    def test_get_ticker(self, mock_connector):
        ticker = mock_connector.get_ticker("BTC/USD")
        assert ticker.pair == "BTC/USD"
        assert ticker.last == 60000.0
        assert ticker.bid < ticker.last
        assert ticker.ask > ticker.last

    def test_get_ticker_unknown_pair(self, mock_connector):
        with pytest.raises(ValueError, match="Unknown pair"):
            mock_connector.get_ticker("FAKE/USD")

    def test_get_orderbook(self, mock_connector):
        book = mock_connector.get_orderbook("BTC/USD", depth=5)
        assert book.pair == "BTC/USD"
        assert len(book.bids) == 5
        assert len(book.asks) == 5
        assert book.bids[0].price < 60000.0
        assert book.asks[0].price > 60000.0

    def test_get_candles(self, mock_connector):
        candles = mock_connector.get_candles("ETH/USD", timeframe="1h", limit=10)
        assert len(candles) == 10
        assert candles[0].timestamp_ms < candles[-1].timestamp_ms

    def test_place_market_order(self, mock_connector):
        order = mock_connector.place_order(
            pair="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.5,
        )
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 0.5
        assert order.pair == "BTC/USD"

    def test_place_limit_order(self, mock_connector):
        order = mock_connector.place_order(
            pair="ETH/USD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=2.0,
            price=3100.0,
        )
        assert order.status == OrderStatus.OPEN
        assert order.filled_quantity == 0.0
        assert order.price == 3100.0

    def test_cancel_order(self, mock_connector):
        order = mock_connector.place_order(
            pair="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=2900.0,
        )
        cancelled = mock_connector.cancel_order(order.id)
        assert cancelled.status == OrderStatus.CANCELLED

    def test_cancel_filled_order_raises(self, mock_connector):
        order = mock_connector.place_order(
            pair="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1,
        )
        with pytest.raises(ValueError, match="Cannot cancel"):
            mock_connector.cancel_order(order.id)

    def test_cancel_unknown_order_raises(self, mock_connector):
        with pytest.raises(ValueError, match="Order not found"):
            mock_connector.cancel_order("nonexistent")

    def test_get_balances(self, mock_connector):
        balances = mock_connector.get_balances()
        assert len(balances) == 3
        usd = next(b for b in balances if b.currency == "USD")
        assert usd.available == 10000.0
        assert usd.total == 10000.0

    def test_get_pairs(self, mock_connector):
        pairs = mock_connector.get_pairs()
        assert "BTC/USD" in pairs
        assert "ETH/USD" in pairs

    def test_set_price(self, mock_connector):
        mock_connector.set_price("BTC/USD", 70000.0)
        ticker = mock_connector.get_ticker("BTC/USD")
        assert ticker.last == 70000.0


class TestExchangeRegistry:
    def test_register_and_get(self, registry, mock_connector):
        assert registry.get("mock") is mock_connector

    def test_list_exchanges(self, registry):
        assert registry.list_exchanges() == ["mock"]

    def test_get_unknown(self, registry):
        assert registry.get("nonexistent") is None

    def test_remove(self, registry):
        assert registry.remove("mock") is True
        assert registry.get("mock") is None
        assert registry.remove("mock") is False

    def test_contains(self, registry):
        assert "mock" in registry
        assert "other" not in registry

    def test_len(self, registry):
        assert len(registry) == 1

    def test_multiple_connectors(self):
        reg = ExchangeRegistry()
        reg.register(MockExchangeConnector(exchange_name="exchange_a"))
        reg.register(MockExchangeConnector(exchange_name="exchange_b"))
        assert len(reg) == 2
        assert sorted(reg.list_exchanges()) == ["exchange_a", "exchange_b"]


class TestExchangeAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_list_exchanges(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["name"] == "mock"

    def test_get_pairs(self, client):
        resp = client.get("/mock/pairs")
        assert resp.status_code == 200
        body = resp.json()
        pair_names = [item["attributes"]["pair"] for item in body["data"]]
        assert "BTC/USD" in pair_names

    def test_get_pairs_unknown_exchange(self, client):
        resp = client.get("/nonexistent/pairs")
        assert resp.status_code == 404

    def test_get_ticker(self, client):
        resp = client.get("/mock/ticker/BTC/USD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["last"] == 60000.0
        assert body["data"]["attributes"]["pair"] == "BTC/USD"

    def test_get_ticker_unknown_exchange(self, client):
        resp = client.get("/nonexistent/ticker/BTC/USD")
        assert resp.status_code == 404

    def test_get_ticker_unknown_pair(self, client):
        resp = client.get("/mock/ticker/FAKE/USD")
        assert resp.status_code == 404
