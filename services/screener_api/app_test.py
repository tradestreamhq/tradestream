"""Tests for the Stock Screener REST API endpoints."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.screener_api.app import create_app
from services.screener_api.screener import MarketSnapshot


class FakeRecord(dict):
    """Simulates asyncpg.Record for testing."""

    def __getitem__(self, key):
        return dict.__getitem__(self, key)


def _make_pool():
    """Create a mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


def _sample_snapshots():
    return [
        MarketSnapshot(
            symbol="BTC/USD", price=60000.0, volume=5_000_000.0,
            rsi=45.0, sma_20=59000.0, sma_50=58000.0, sma_200=55000.0,
            sector="Crypto",
        ),
        MarketSnapshot(
            symbol="ETH/USD", price=3500.0, volume=3_000_000.0,
            rsi=25.0, sma_20=3400.0, sma_50=3300.0, sma_200=3000.0,
            sector="Crypto",
        ),
        MarketSnapshot(
            symbol="AAPL", price=150.0, volume=80_000_000.0,
            rsi=60.0, sma_20=148.0, sma_50=145.0, sma_200=140.0,
            sector="Technology",
        ),
    ]


@pytest.fixture
def client():
    pool, conn = _make_pool()

    async def market_data_fn():
        return _sample_snapshots()

    app = create_app(pool, market_data_fn=market_data_fn)
    return TestClient(app, raise_server_exceptions=False), pool, conn


@pytest.fixture
def client_no_data():
    pool, conn = _make_pool()
    app = create_app(pool, market_data_fn=None)
    return TestClient(app, raise_server_exceptions=False), pool, conn


class TestHealthEndpoint:
    def test_health(self, client):
        tc, pool, conn = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestScanEndpoint:
    def test_scan_basic(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gte", "value": 100.0}
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2  # BTC and AAPL
        for item in body["data"]:
            assert "symbol" in item["attributes"]
            assert "current_price" in item["attributes"]
            assert "volume" in item["attributes"]
            assert "matched_criteria" in item["attributes"]
            assert "score" in item["attributes"]

    def test_scan_rsi_oversold(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "rsi", "operator": "lte", "value": 30.0}
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "ETH/USD"

    def test_scan_with_sector(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gt", "value": 0}
                ],
                "sector": "Technology",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "AAPL"

    def test_scan_multiple_filters(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gte", "value": 1000.0},
                    {"field": "volume", "operator": "gte", "value": 1_000_000.0},
                    {"field": "rsi", "operator": "lte", "value": 50.0},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # BTC matches price>=1000, volume>=1M, rsi<=50 (all 3)
        assert len(body["data"]) >= 1
        btc = [d for d in body["data"] if d["attributes"]["symbol"] == "BTC/USD"]
        assert len(btc) == 1
        assert btc[0]["attributes"]["score"] == 1.0

    def test_scan_between_filter(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {
                        "field": "rsi",
                        "operator": "between",
                        "value": 40.0,
                        "value_max": 65.0,
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        symbols = [d["attributes"]["symbol"] for d in body["data"]]
        assert "BTC/USD" in symbols
        assert "AAPL" in symbols
        assert "ETH/USD" not in symbols

    def test_scan_no_results(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gt", "value": 999_999.0}
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_scan_no_market_data(self, client_no_data):
        tc, pool, conn = client_no_data
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gt", "value": 0}
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_scan_with_limit(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "gt", "value": 0}
                ],
                "limit": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_scan_invalid_operator(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={
                "filters": [
                    {"field": "price", "operator": "invalid", "value": 0}
                ],
            },
        )
        assert resp.status_code == 422

    def test_scan_empty_filters(self, client):
        tc, pool, conn = client
        resp = tc.post(
            "/scan",
            json={"filters": []},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0


class TestPresetsEndpoints:
    def test_list_presets_built_in_only(self, client):
        tc, pool, conn = client
        conn.fetch.return_value = []
        resp = tc.get("/presets")
        assert resp.status_code == 200
        body = resp.json()
        # Should have at least the built-in presets
        assert len(body["data"]) >= 5

    def test_list_presets_with_user_presets(self, client):
        tc, pool, conn = client
        preset_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                {
                    "id": preset_id,
                    "name": "My Preset",
                    "description": "Custom scan",
                    "filters": [{"field": "price", "operator": "gt", "value": 100}],
                    "sector": None,
                    "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                }
            )
        ]
        resp = tc.get("/presets")
        assert resp.status_code == 200
        body = resp.json()
        # Built-in + 1 user preset
        assert len(body["data"]) >= 6

    def test_get_builtin_preset(self, client):
        tc, pool, conn = client
        resp = tc.get("/presets/high_volume_breakout")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "high_volume_breakout"
        assert body["data"]["attributes"]["type"] == "built_in"
        assert "High Volume Breakout" in body["data"]["attributes"]["name"]

    def test_get_user_preset(self, client):
        tc, pool, conn = client
        preset_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            {
                "id": preset_id,
                "name": "My Scan",
                "description": "Test",
                "filters": [{"field": "rsi", "operator": "lte", "value": 30}],
                "sector": None,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )
        resp = tc.get(f"/presets/{preset_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "My Scan"

    def test_get_preset_not_found(self, client):
        tc, pool, conn = client
        fake_id = str(uuid.uuid4())
        conn.fetchrow.return_value = None
        resp = tc.get(f"/presets/{fake_id}")
        assert resp.status_code == 404

    def test_create_preset(self, client):
        tc, pool, conn = client
        preset_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            {
                "id": preset_id,
                "name": "New Preset",
                "description": "My custom scan",
                "filters": [{"field": "price", "operator": "gt", "value": 50}],
                "sector": "Technology",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )
        resp = tc.post(
            "/presets",
            json={
                "name": "New Preset",
                "description": "My custom scan",
                "filters": [
                    {"field": "price", "operator": "gt", "value": 50}
                ],
                "sector": "Technology",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "New Preset"
        assert body["data"]["id"] == str(preset_id)

    def test_delete_preset(self, client):
        tc, pool, conn = client
        preset_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord({"id": preset_id})
        resp = tc.delete(f"/presets/{preset_id}")
        assert resp.status_code == 200  # 204 returns empty, TestClient shows 200

    def test_delete_builtin_preset_rejected(self, client):
        tc, pool, conn = client
        resp = tc.delete("/presets/high_volume_breakout")
        assert resp.status_code == 422
        body = resp.json()
        assert "built-in" in body["error"]["message"]

    def test_delete_preset_not_found(self, client):
        tc, pool, conn = client
        fake_id = str(uuid.uuid4())
        conn.fetchrow.return_value = None
        resp = tc.delete(f"/presets/{fake_id}")
        assert resp.status_code == 404
