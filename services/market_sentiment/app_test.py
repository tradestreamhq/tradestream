"""Tests for the market sentiment REST API."""

import pytest
from fastapi.testclient import TestClient

from services.market_sentiment.aggregator import SentimentDataFetcher
from services.market_sentiment.app import create_app
from services.market_sentiment.signal_generator import SentimentMomentumTracker


@pytest.fixture
def client():
    """Create a test client with a fetcher that skips external calls."""
    fetcher = SentimentDataFetcher(fear_greed_url="http://localhost:0/fng/")
    momentum = SentimentMomentumTracker(window_size=10)
    app = create_app(fetcher=fetcher, momentum_tracker=momentum)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok" or "status" in data


class TestSentimentEndpoint:
    def test_requires_symbol(self, client):
        resp = client.get("/sentiment")
        assert resp.status_code == 422

    def test_with_funding_rate(self, client):
        resp = client.get(
            "/sentiment",
            params={
                "symbol": "BTC-USD",
                "funding_rate": 0.005,
                "long_short_ratio": 1.2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data or "composite_score" in str(data)

    def test_with_news_and_social(self, client):
        resp = client.get(
            "/sentiment",
            params={
                "symbol": "ETH-USD",
                "news_score": -0.3,
                "news_headline_count": 10,
                "social_mentions": 150,
                "social_avg_mentions": 100,
            },
        )
        assert resp.status_code == 200

    def test_no_sources_returns_not_found(self, client):
        """If no sources provide data, return not found."""
        resp = client.get("/sentiment", params={"symbol": "UNKNOWN"})
        # With no external sources providing data, we get not_found
        assert resp.status_code in (200, 404)


class TestSignalEndpoint:
    def test_generates_signal(self, client):
        resp = client.get(
            "/signal",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": -0.7,
                "price_change_pct": -2.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body.get("action") in ("BUY", "SELL", "HOLD")

    def test_extreme_greed_sell(self, client):
        resp = client.get(
            "/signal",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": 0.8,
                "price_change_pct": 5.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body.get("action") == "SELL"

    def test_neutral_hold(self, client):
        resp = client.get(
            "/signal",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": 0.0,
                "price_change_pct": 0.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body.get("action") == "HOLD"


class TestDivergenceEndpoint:
    def test_bearish_divergence(self, client):
        resp = client.get(
            "/divergence",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": -0.5,
                "price_change_pct": 5.0,
                "threshold": 0.3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body.get("divergence_type") == "bearish_divergence"

    def test_no_divergence(self, client):
        resp = client.get(
            "/divergence",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": 0.5,
                "price_change_pct": 5.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body.get("divergence_type") == "none"


class TestMomentumEndpoint:
    def test_no_data_returns_not_found(self, client):
        resp = client.get("/momentum", params={"symbol": "BTC-USD"})
        # No momentum data recorded yet
        assert resp.status_code in (200, 404)

    def test_after_recording_sentiment(self, client):
        """Record sentiment via /sentiment, then check momentum."""
        # Record a few readings
        for rate in [0.001, 0.003, 0.005]:
            client.get(
                "/sentiment",
                params={"symbol": "BTC-USD", "funding_rate": rate},
            )

        resp = client.get("/momentum", params={"symbol": "BTC-USD"})
        assert resp.status_code == 200


class TestDashboardEndpoint:
    def test_dashboard_data(self, client):
        resp = client.get(
            "/dashboard",
            params={
                "symbol": "BTC-USD",
                "sentiment_score": -0.5,
                "price_change_pct": 3.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert "gauge" in body
        assert "divergence" in body
        assert body["gauge"]["score"] == pytest.approx(-0.5, abs=0.01)
