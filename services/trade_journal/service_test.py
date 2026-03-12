"""Tests for the Trade Journal service."""

import csv
import io
import json
from unittest.mock import patch

import pytest

from services.trade_journal.journal import TradeJournal
from services.trade_journal.service import create_app


@pytest.fixture
def journal():
    return TradeJournal()


@pytest.fixture
def app(journal):
    flask_app = create_app(journal=journal)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


SAMPLE_ENTRY = {
    "trade_id": "trade-001",
    "strategy": "momentum",
    "symbol": "BTC-USD",
    "side": "BUY",
    "entry_price": 50000.0,
    "entry_rationale": "RSI oversold with bullish divergence",
    "signals_at_entry": {"rsi": 28, "macd": "bullish_cross"},
    "tags": ["crypto", "momentum"],
}


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "trade-journal"


class TestCreateEntry:
    def test_create_entry(self, client):
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["trade_id"] == "trade-001"
        assert data["strategy"] == "momentum"
        assert data["symbol"] == "BTC-USD"
        assert data["side"] == "BUY"
        assert data["entry_price"] == 50000.0
        assert data["outcome"] == "OPEN"
        assert data["signals_at_entry"]["rsi"] == 28

    def test_create_entry_missing_fields(self, client):
        resp = client.post("/journal/entries", json={"trade_id": "t1"})
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

    def test_create_entry_no_body(self, client):
        resp = client.post("/journal/entries")
        assert resp.status_code == 400

    def test_create_entry_invalid_side(self, client):
        data = {**SAMPLE_ENTRY, "side": "INVALID"}
        resp = client.post("/journal/entries", json=data)
        assert resp.status_code == 400


class TestCloseEntry:
    def test_close_entry_win(self, client):
        # Create entry
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        entry_id = resp.get_json()["id"]

        # Close with profit
        resp = client.post(
            f"/journal/entries/{entry_id}/close",
            json={
                "exit_price": 55000.0,
                "exit_rationale": "Target reached",
                "lessons": "Patience paid off",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["outcome"] == "WIN"
        assert data["pnl"] == 5000.0
        assert data["exit_price"] == 55000.0
        assert data["lessons"] == "Patience paid off"

    def test_close_entry_loss(self, client):
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        entry_id = resp.get_json()["id"]

        resp = client.post(
            f"/journal/entries/{entry_id}/close",
            json={"exit_price": 48000.0, "exit_rationale": "Stop loss hit"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["outcome"] == "LOSS"
        assert data["pnl"] == -2000.0

    def test_close_entry_not_found(self, client):
        resp = client.post(
            "/journal/entries/nonexistent/close",
            json={"exit_price": 50000.0, "exit_rationale": "test"},
        )
        assert resp.status_code == 404

    def test_close_entry_missing_fields(self, client):
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        entry_id = resp.get_json()["id"]

        resp = client.post(
            f"/journal/entries/{entry_id}/close",
            json={"exit_price": 50000.0},
        )
        assert resp.status_code == 400


class TestGetEntry:
    def test_get_entry(self, client):
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        entry_id = resp.get_json()["id"]

        resp = client.get(f"/journal/entries/{entry_id}")
        assert resp.status_code == 200
        assert resp.get_json()["trade_id"] == "trade-001"

    def test_get_entry_not_found(self, client):
        resp = client.get("/journal/entries/nonexistent")
        assert resp.status_code == 404


class TestListEntries:
    def test_list_all(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "trade-002", "symbol": "ETH-USD"})

        resp = client.get("/journal/entries")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2

    def test_filter_by_strategy(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2", "strategy": "mean_reversion"})

        resp = client.get("/journal/entries?strategy=momentum")
        assert resp.get_json()["count"] == 1

    def test_filter_by_symbol(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2", "symbol": "ETH-USD"})

        resp = client.get("/journal/entries?symbol=ETH-USD")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["entries"][0]["symbol"] == "ETH-USD"

    def test_filter_by_outcome(self, client):
        # Create and close with a win
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        entry_id = resp.get_json()["id"]
        client.post(
            f"/journal/entries/{entry_id}/close",
            json={"exit_price": 55000.0, "exit_rationale": "target"},
        )

        # Create an open entry
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2"})

        resp = client.get("/journal/entries?outcome=WIN")
        assert resp.get_json()["count"] == 1

    def test_filter_by_tags(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2", "tags": ["forex"]})

        resp = client.get("/journal/entries?tags=crypto")
        assert resp.get_json()["count"] == 1


class TestSummary:
    def test_summary_empty(self, client):
        resp = client.get("/journal/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_entries"] == 0
        assert data["win_rate"] == 0.0

    def test_summary_with_closed_trades(self, client):
        # Win
        resp = client.post("/journal/entries", json=SAMPLE_ENTRY)
        eid = resp.get_json()["id"]
        client.post(f"/journal/entries/{eid}/close", json={"exit_price": 55000, "exit_rationale": "tp"})

        # Loss
        resp = client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2"})
        eid = resp.get_json()["id"]
        client.post(f"/journal/entries/{eid}/close", json={"exit_price": 48000, "exit_rationale": "sl"})

        resp = client.get("/journal/summary")
        data = resp.get_json()
        assert data["closed_entries"] == 2
        assert data["wins"] == 1
        assert data["losses"] == 1
        assert data["win_rate"] == 50.0
        assert data["total_pnl"] == 3000.0


class TestExportCSV:
    def test_export_csv(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)

        resp = client.get("/journal/export/csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"

        reader = csv.DictReader(io.StringIO(resp.data.decode()))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["trade_id"] == "trade-001"
        assert rows[0]["strategy"] == "momentum"

    def test_export_csv_with_filter(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)
        client.post("/journal/entries", json={**SAMPLE_ENTRY, "trade_id": "t2", "symbol": "ETH-USD"})

        resp = client.get("/journal/export/csv?symbol=ETH-USD")
        reader = csv.DictReader(io.StringIO(resp.data.decode()))
        rows = list(reader)
        assert len(rows) == 1


class TestExportJSON:
    def test_export_json(self, client):
        client.post("/journal/entries", json=SAMPLE_ENTRY)

        resp = client.get("/journal/export/json")
        assert resp.status_code == 200
        assert resp.content_type == "application/json; charset=utf-8"

        data = json.loads(resp.data)
        assert len(data) == 1
        assert data[0]["trade_id"] == "trade-001"


class TestJournalUnit:
    """Unit tests for the TradeJournal class directly."""

    def test_log_and_close(self, journal):
        entry = journal.log_entry(
            trade_id="t1",
            strategy="test",
            symbol="BTC-USD",
            side="BUY",
            entry_price=100.0,
            entry_rationale="test entry",
        )
        assert entry.outcome.value == "OPEN"

        closed = journal.close_entry(entry.id, 110.0, "test exit")
        assert closed.outcome.value == "WIN"
        assert closed.pnl == 10.0

    def test_sell_side_pnl(self, journal):
        entry = journal.log_entry(
            trade_id="t1",
            strategy="test",
            symbol="BTC-USD",
            side="SELL",
            entry_price=100.0,
            entry_rationale="short entry",
        )
        closed = journal.close_entry(entry.id, 90.0, "covered")
        assert closed.pnl == 10.0
        assert closed.outcome.value == "WIN"

    def test_breakeven(self, journal):
        entry = journal.log_entry(
            trade_id="t1",
            strategy="test",
            symbol="BTC-USD",
            side="BUY",
            entry_price=100.0,
            entry_rationale="test",
        )
        closed = journal.close_entry(entry.id, 100.0, "flat")
        assert closed.outcome.value == "BREAKEVEN"
        assert closed.pnl == 0.0

    def test_close_nonexistent_raises(self, journal):
        with pytest.raises(KeyError):
            journal.close_entry("bad-id", 100.0, "test")

    def test_all_entries(self, journal):
        journal.log_entry("t1", "s1", "BTC-USD", "BUY", 100.0, "r1")
        journal.log_entry("t2", "s2", "ETH-USD", "SELL", 200.0, "r2")
        assert len(journal.all_entries()) == 2


class TestModels:
    def test_to_dict_from_dict_roundtrip(self):
        from services.trade_journal.models import JournalEntry

        entry = JournalEntry(
            trade_id="t1",
            strategy="momentum",
            symbol="BTC-USD",
            side="BUY",
            entry_price=50000.0,
            entry_rationale="test",
            signals_at_entry={"rsi": 30},
            tags=["crypto"],
        )
        d = entry.to_dict()
        restored = JournalEntry.from_dict(d)
        assert restored.trade_id == entry.trade_id
        assert restored.signals_at_entry == {"rsi": 30}
        assert restored.tags == ["crypto"]
