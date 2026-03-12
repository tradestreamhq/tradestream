"""Tests for the Order Book REST API."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.orderbook_api.app import create_app


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


SAMPLE_BIDS = [[50000.0, 1.5], [49999.0, 2.0], [49998.0, 0.8]]
SAMPLE_ASKS = [[50001.0, 1.0], [50002.0, 3.0], [50003.0, 0.5]]
SAMPLE_TS = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)


def _snapshot_row(**overrides):
    base = FakeRecord(
        id="00000000-0000-0000-0000-000000000001",
        symbol="BTC/USD",
        exchange="binance",
        bids=json.dumps(SAMPLE_BIDS),
        asks=json.dumps(SAMPLE_ASKS),
        timestamp=SAMPLE_TS,
        sequence_number=42,
    )
    base.update(overrides)
    return base


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestGetOrderbook:
    def test_returns_snapshot(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["exchange"] == "binance"
        assert len(attrs["bids"]) == 3
        assert len(attrs["asks"]) == 3
        assert attrs["sequence_number"] == 42

    def test_respects_depth(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD?depth=2")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert len(attrs["bids"]) == 2
        assert len(attrs["asks"]) == 2
        assert attrs["depth"] == 2

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/orderbook/DOGE%2FUSD")
        assert resp.status_code == 404

    def test_depth_validation(self, client):
        tc, conn = client
        resp = tc.get("/orderbook/BTC%2FUSD?depth=0")
        assert resp.status_code == 422


class TestGetSpread:
    def test_returns_spread(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD/spread")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["best_bid"] == 50000.0
        assert attrs["best_ask"] == 50001.0
        assert attrs["spread"] == 1.0
        assert attrs["mid_price"] == 50000.5
        assert attrs["spread_percentage"] > 0

    def test_spread_percentage_calculation(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD/spread")
        attrs = resp.json()["data"]["attributes"]
        expected_pct = round(1.0 / 50000.5 * 100, 6)
        assert attrs["spread_percentage"] == expected_pct

    def test_empty_book(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row(
            bids=json.dumps([]), asks=json.dumps([])
        )

        resp = tc.get("/orderbook/BTC%2FUSD/spread")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["best_bid"] is None
        assert attrs["spread"] is None

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/orderbook/DOGE%2FUSD/spread")
        assert resp.status_code == 404


class TestGetImbalance:
    def test_returns_imbalance(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD/imbalance")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # bid_volume = 1.5 + 2.0 + 0.8 = 4.3
        # ask_volume = 1.0 + 3.0 + 0.5 = 4.5
        assert attrs["bid_volume"] == 4.3
        assert attrs["ask_volume"] == 4.5
        assert attrs["total_volume"] == 8.8
        expected_imbalance = round((4.3 - 4.5) / 8.8, 6)
        assert attrs["imbalance"] == expected_imbalance

    def test_imbalance_with_depth(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row()

        resp = tc.get("/orderbook/BTC%2FUSD/imbalance?depth=1")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # Only top level: bid=1.5, ask=1.0
        assert attrs["bid_volume"] == 1.5
        assert attrs["ask_volume"] == 1.0
        expected_imbalance = round((1.5 - 1.0) / 2.5, 6)
        assert attrs["imbalance"] == expected_imbalance

    def test_balanced_book(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row(
            bids=json.dumps([[100.0, 5.0]]),
            asks=json.dumps([[101.0, 5.0]]),
        )

        resp = tc.get("/orderbook/BTC%2FUSD/imbalance")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["imbalance"] == 0.0

    def test_empty_book_imbalance(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _snapshot_row(
            bids=json.dumps([]), asks=json.dumps([])
        )

        resp = tc.get("/orderbook/BTC%2FUSD/imbalance")
        attrs = resp.json()["data"]["attributes"]
        assert attrs["imbalance"] == 0
        assert attrs["total_volume"] == 0

    def test_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/orderbook/DOGE%2FUSD/imbalance")
        assert resp.status_code == 404


class TestGetHistory:
    def test_returns_history(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                bucket=datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc),
                avg_spread=1.5,
                avg_mid_price=50000.0,
                avg_spread_percentage=0.003,
                avg_imbalance=-0.05,
                sample_count=12,
            ),
            FakeRecord(
                bucket=datetime(2026, 3, 12, 9, 59, tzinfo=timezone.utc),
                avg_spread=2.0,
                avg_mid_price=49999.0,
                avg_spread_percentage=0.004,
                avg_imbalance=0.1,
                sample_count=10,
            ),
        ]

        resp = tc.get("/orderbook/BTC%2FUSD/history?interval=1m&limit=60")
        assert resp.status_code == 200
        body = resp.json()
        # Returns in chronological order (reversed from DB query)
        assert len(body["data"]) == 2
        first = body["data"][0]["attributes"]
        assert first["avg_spread"] == 2.0
        assert first["sample_count"] == 10

    def test_invalid_interval(self, client):
        tc, conn = client

        resp = tc.get("/orderbook/BTC%2FUSD/history?interval=2m")
        assert resp.status_code == 422

    def test_empty_history(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/orderbook/BTC%2FUSD/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0
