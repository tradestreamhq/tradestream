"""Tests for the Market Data WebSocket Gateway."""

import pytest
from starlette.testclient import TestClient

from services.market_data_ws.app import create_app
from services.market_data_ws.broadcaster import MarketDataBroadcaster


@pytest.fixture
def broadcaster():
    return MarketDataBroadcaster()


@pytest.fixture
def client(broadcaster):
    app = create_app(broadcaster=broadcaster, max_connections_per_client=2)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestWebSocketConnection:
    def test_connect_receives_welcome(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert "heartbeat_interval" in msg
            assert "max_connections" in msg

    def test_max_connections_per_client(self, client):
        with client.websocket_connect("/ws/market-data") as ws1:
            ws1.receive_json()  # welcome
            with client.websocket_connect("/ws/market-data") as ws2:
                ws2.receive_json()  # welcome
                with client.websocket_connect("/ws/market-data") as ws3:
                    msg = ws3.receive_json()
                    assert msg["type"] == "error"
                    assert msg["error"] == "max_connections_exceeded"


class TestSubscriptions:
    def test_subscribe_valid_channel(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"
            assert msg["channel"] == "trades:BTC-USD"
            assert msg["already_subscribed"] is False

    def test_subscribe_duplicate(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            ws.receive_json()  # first subscribe ack
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"
            assert msg["already_subscribed"] is True

    def test_subscribe_invalid_channel(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "invalid"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error"] == "invalid_channel"

    def test_subscribe_candles_requires_interval(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "candles:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error"] == "invalid_channel"

    def test_subscribe_candles_with_interval(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "candles:ETH-USD:1m"})
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"
            assert msg["channel"] == "candles:ETH-USD:1m"

    def test_subscribe_orderbook(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "orderbook:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "subscribed"

    def test_unsubscribe(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            ws.receive_json()  # subscribe ack
            ws.send_json({"type": "unsubscribe", "channel": "trades:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "unsubscribed"
            assert msg["was_subscribed"] is True

    def test_unsubscribe_not_subscribed(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "unsubscribe", "channel": "trades:BTC-USD"})
            msg = ws.receive_json()
            assert msg["type"] == "unsubscribed"
            assert msg["was_subscribed"] is False

    def test_list_subscriptions(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            ws.receive_json()
            ws.send_json({"type": "subscribe", "channel": "candles:ETH-USD:1m"})
            ws.receive_json()
            ws.send_json({"type": "list_subscriptions"})
            msg = ws.receive_json()
            assert msg["type"] == "subscriptions"
            assert sorted(msg["channels"]) == [
                "candles:ETH-USD:1m",
                "trades:BTC-USD",
            ]


class TestPingPong:
    def test_ping_returns_pong(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"
            assert "timestamp" in msg


class TestUnknownMessage:
    def test_unknown_type(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "foobar"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error"] == "unknown_message_type"


class TestBroadcaster:
    def test_validate_channel_valid(self):
        assert MarketDataBroadcaster.validate_channel("trades:BTC-USD")
        assert MarketDataBroadcaster.validate_channel("candles:ETH-USD:1m")
        assert MarketDataBroadcaster.validate_channel("orderbook:BTC-USD")

    def test_validate_channel_invalid(self):
        assert not MarketDataBroadcaster.validate_channel("invalid")
        assert not MarketDataBroadcaster.validate_channel("foo:bar")
        assert not MarketDataBroadcaster.validate_channel("trades")
        assert not MarketDataBroadcaster.validate_channel(
            "candles:BTC-USD"
        )  # missing interval
        assert not MarketDataBroadcaster.validate_channel(
            "trades:BTC-USD:extra"
        )  # extra segment
        assert not MarketDataBroadcaster.validate_channel("orderbook:BTC-USD:extra")


class TestBroadcast:
    def test_broadcast_to_subscriber(self, client, broadcaster):
        with client.websocket_connect("/ws/market-data") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "trades:BTC-USD"})
            ws.receive_json()  # subscribe ack

            import asyncio

            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                broadcaster.broadcast(
                    "trades:BTC-USD",
                    {"price": 50000.0, "size": 1.5},
                )
            )
            loop.close()

            msg = ws.receive_json()
            assert msg["type"] == "data"
            assert msg["channel"] == "trades:BTC-USD"
            assert msg["payload"]["price"] == 50000.0
