"""Tests for the Sentiment Analysis REST API."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from services.sentiment_api.app import create_app
from services.sentiment_api.analyzer import SentimentAnalyzer


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.health_check.return_value = None
    return provider


@pytest.fixture
def client(mock_provider):
    analyzer = SentimentAnalyzer(whale_threshold=50_000.0)
    app = create_app(mock_provider, analyzer)
    return TestClient(app, raise_server_exceptions=False), mock_provider


class TestHealthEndpoints:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestGetSentiment:
    def test_sentiment_snapshot(self, client):
        tc, provider = client
        provider.get_order_book.return_value = {
            "bids": [
                {"price": 60000.0, "size": 5.0},
                {"price": 59990.0, "size": 3.0},
            ],
            "asks": [
                {"price": 60010.0, "size": 2.0},
                {"price": 60020.0, "size": 1.0},
            ],
        }
        provider.get_recent_trades.return_value = [
            {
                "side": "buy",
                "price": 60000.0,
                "size": 2.0,
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "side": "sell",
                "price": 60000.0,
                "size": 1.0,
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]
        provider.get_funding_rate.return_value = 0.0001

        resp = tc.get("/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "BTC/USD"
        attrs = body["data"]["attributes"]
        assert attrs["pair"] == "BTC/USD"
        assert -1.0 <= attrs["composite_score"] <= 1.0
        assert attrs["order_book_imbalance"] is not None
        assert attrs["trade_flow"] is not None

    def test_sentiment_not_found(self, client):
        tc, provider = client
        provider.get_order_book.return_value = None
        resp = tc.get("/UNKNOWN%2FUSD")
        assert resp.status_code == 404

    def test_custom_levels_and_window(self, client):
        tc, provider = client
        provider.get_order_book.return_value = {
            "bids": [{"price": 100.0, "size": 1.0}],
            "asks": [{"price": 101.0, "size": 1.0}],
        }
        provider.get_recent_trades.return_value = []
        provider.get_funding_rate.return_value = None

        resp = tc.get("/TEST%2FUSD?levels=5&window=60")
        assert resp.status_code == 200
        provider.get_order_book.assert_called_with("TEST/USD", 5)
        provider.get_recent_trades.assert_called_with("TEST/USD", 60)


class TestSentimentHistory:
    def test_history(self, client):
        tc, provider = client
        provider.get_sentiment_history.return_value = [
            {
                "pair": "BTC/USD",
                "composite_score": 0.5,
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "pair": "BTC/USD",
                "composite_score": -0.2,
                "timestamp": "2026-01-01T00:05:00Z",
            },
        ]
        resp = tc.get("/BTC%2FUSD/history?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["meta"]["limit"] == 10

    def test_history_not_found(self, client):
        tc, provider = client
        provider.get_sentiment_history.return_value = None
        resp = tc.get("/BAD%2FUSD/history")
        assert resp.status_code == 404


class TestWhaleTrades:
    def test_whale_trades(self, client):
        tc, provider = client
        provider.get_whale_trades.return_value = [
            {
                "pair": "BTC/USD",
                "side": "buy",
                "price": 60000.0,
                "size": 2.0,
                "notional": 120000.0,
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ]
        resp = tc.get("/BTC%2FUSD/whale-trades")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["side"] == "buy"

    def test_whale_trades_with_threshold(self, client):
        tc, provider = client
        provider.get_whale_trades.return_value = []
        resp = tc.get("/BTC%2FUSD/whale-trades?threshold=200000")
        assert resp.status_code == 200
        provider.get_whale_trades.assert_called_with(
            "BTC/USD", limit=50, threshold=200000.0
        )

    def test_whale_trades_not_found(self, client):
        tc, provider = client
        provider.get_whale_trades.return_value = None
        resp = tc.get("/BAD%2FUSD/whale-trades")
        assert resp.status_code == 404
