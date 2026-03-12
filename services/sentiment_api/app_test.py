"""Tests for the Sentiment Analysis API."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from services.sentiment_api.app import create_app
from services.sentiment_api.feed_processor import SentimentStore


@pytest.fixture
def store():
    return SentimentStore()


@pytest.fixture
def client(store):
    app = create_app(store)
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestIngest:
    def test_ingest_text(self, client):
        resp = client.post(
            "/ingest",
            json={
                "text": "BTC is surging with a massive bullish rally",
                "symbol": "BTC/USD",
                "source": "twitter",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["type"] == "sentiment_record"
        assert data["attributes"]["score"] > 0

    def test_ingest_with_timestamp(self, client):
        resp = client.post(
            "/ingest",
            json={
                "text": "market is crashing hard, panic selling",
                "symbol": "ETH/USD",
                "source": "news",
                "timestamp": "2026-03-01T12:00:00",
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["score"] < 0
        assert attrs["timestamp"].startswith("2026-03-01")

    def test_ingest_empty_text(self, client):
        resp = client.post(
            "/ingest",
            json={"text": "", "symbol": "BTC/USD", "source": "test"},
        )
        assert resp.status_code == 422


class TestGetSentiment:
    def test_get_sentiment_no_data(self, client):
        resp = client.get("/BTC%2FUSD")
        assert resp.status_code == 404

    def test_get_sentiment_with_data(self, client, store):
        store.ingest_text("bullish rally surge", "BTC/USD", "twitter",
                          datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bearish crash dump", "BTC/USD", "news",
                          datetime(2026, 3, 1, 11, 0))

        resp = client.get("/BTC%2FUSD")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "average_score" in attrs
        assert attrs["record_count"] == 2
        assert "velocity" in attrs

    def test_get_sentiment_time_range(self, client, store):
        store.ingest_text("bullish", "BTC/USD", "twitter",
                          datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bearish", "BTC/USD", "twitter",
                          datetime(2026, 3, 2, 10, 0))

        resp = client.get(
            "/BTC%2FUSD",
            params={"from": "2026-03-02T00:00:00", "to": "2026-03-03T00:00:00"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["record_count"] == 1


class TestGetRecords:
    def test_get_records(self, client, store):
        store.ingest_text("bullish rally", "BTC/USD", "twitter",
                          datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bearish dump", "BTC/USD", "news",
                          datetime(2026, 3, 1, 11, 0))

        resp = client.get("/BTC%2FUSD/records")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_get_records_empty(self, client):
        resp = client.get("/ETH%2FUSD/records")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
