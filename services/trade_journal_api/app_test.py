"""Tests for the Trade Journal REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.trade_journal_api.app import create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


_ENTRY_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _sample_entry_row(**overrides):
    defaults = dict(
        id=_ENTRY_ID,
        instrument="BTC/USD",
        side="BUY",
        entry_price=50000.0,
        exit_price=52000.0,
        size=0.5,
        pnl=1000.0,
        outcome="WIN",
        strategy_name="sma_crossover",
        signal_trigger="SMA(20) crossed above SMA(50)",
        notes="Strong momentum entry",
        opened_at=_NOW,
        closed_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return FakeRecord(**defaults)


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


class TestCreateEntry:
    def test_create_entry_success(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_entry_row()
        conn.executemany.return_value = None

        resp = tc.post(
            "/entries",
            json={
                "instrument": "BTC/USD",
                "side": "BUY",
                "entry_price": 50000.0,
                "size": 0.5,
                "strategy_name": "sma_crossover",
                "signal_trigger": "SMA(20) crossed above SMA(50)",
                "tags": ["momentum", "crypto"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "journal_entry"
        assert body["data"]["attributes"]["instrument"] == "BTC/USD"
        assert body["data"]["attributes"]["tags"] == ["momentum", "crypto"]

    def test_create_entry_minimal(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_entry_row(
            exit_price=None, pnl=None, outcome="OPEN", strategy_name=None,
            signal_trigger=None, notes="", closed_at=None,
        )

        resp = tc.post(
            "/entries",
            json={"instrument": "ETH/USD", "side": "SELL", "entry_price": 3000.0, "size": 10.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["outcome"] == "OPEN"

    def test_create_entry_invalid_side(self, client):
        tc, _ = client
        resp = tc.post(
            "/entries",
            json={"instrument": "BTC/USD", "side": "HOLD", "entry_price": 50000.0, "size": 1.0},
        )
        assert resp.status_code == 422


class TestListEntries:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_entry_row()],          # entries query
            [FakeRecord(tag="momentum")],   # tags for first entry
        ]

        resp = tc.get("/entries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["tags"] == ["momentum"]

    def test_filter_by_strategy(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_entry_row()],
            [FakeRecord(tag="momentum")],
        ]

        resp = tc.get("/entries?strategy=sma_crossover")
        assert resp.status_code == 200

    def test_filter_by_outcome(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.side_effect = [[]]

        resp = tc.get("/entries?outcome=LOSS")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    def test_search_notes(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_entry_row()],
            [FakeRecord(tag="momentum")],
        ]

        resp = tc.get("/entries?search=momentum")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestGetEntry:
    def test_get_entry_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_entry_row()
        conn.fetch.return_value = [FakeRecord(tag="momentum"), FakeRecord(tag="crypto")]

        resp = tc.get(f"/entries/{_ENTRY_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == str(_ENTRY_ID)
        assert set(body["data"]["attributes"]["tags"]) == {"momentum", "crypto"}

    def test_get_entry_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/entries/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateEntry:
    def test_add_notes_and_tags(self, client):
        tc, conn = client
        # First fetchrow: existence check
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_entry_row(notes="Updated notes"),
        ]
        conn.execute.return_value = None
        conn.executemany.return_value = None

        resp = tc.patch(
            f"/entries/{_ENTRY_ID}",
            json={"notes": "Updated notes", "tags": ["reversal", "mistake"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["tags"] == ["reversal", "mistake"]

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.patch(
            f"/entries/{uuid.uuid4()}",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    def test_close_trade(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_entry_row(exit_price=55000.0, pnl=2500.0, outcome="WIN"),
        ]
        conn.fetch.return_value = [FakeRecord(tag="momentum")]

        resp = tc.patch(
            f"/entries/{_ENTRY_ID}",
            json={
                "exit_price": 55000.0,
                "pnl": 2500.0,
                "outcome": "WIN",
                "closed_at": "2026-03-01T14:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["pnl"] == 2500.0


class TestStats:
    def test_stats_by_tag(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(tag="momentum", total_trades=10, wins=7, losses=3, avg_pnl=150.0, total_pnl=1500.0),
            FakeRecord(tag="reversal", total_trades=5, wins=2, losses=3, avg_pnl=-50.0, total_pnl=-250.0),
        ]

        resp = tc.get("/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

        momentum = body["data"][0]["attributes"]
        assert momentum["tag"] == "momentum"
        assert momentum["win_rate"] == 0.7
        assert momentum["total_pnl"] == 1500.0

        reversal = body["data"][1]["attributes"]
        assert reversal["tag"] == "reversal"
        assert reversal["win_rate"] == 0.4

    def test_stats_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/stats")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0
