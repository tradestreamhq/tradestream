"""Tests for the Export & Report API."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.export_api.app import create_app, _rows_to_csv, _serialize_row


# --- Helpers ---


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


SAMPLE_TRADE = FakeRecord(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    symbol="BTC/USD",
    side="BUY",
    quantity=0.5,
    entry_price=50000.0,
    exit_price=52000.0,
    pnl=1000.0,
    status="CLOSED",
    opened_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
    closed_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
    signal_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
)

SAMPLE_POSITION = FakeRecord(
    symbol="ETH/USD",
    quantity=10.0,
    avg_entry_price=3000.0,
    unrealized_pnl=500.0,
    updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# --- Unit tests for helpers ---


class TestHelpers:
    def test_serialize_row_dates(self):
        row = {"d": date(2026, 3, 1), "dt": datetime(2026, 3, 1, 12, 0)}
        result = _serialize_row(row)
        assert result["d"] == "2026-03-01"
        assert result["dt"] == "2026-03-01T12:00:00"

    def test_serialize_row_passthrough(self):
        row = {"x": 1, "y": "hello", "z": 3.14}
        assert _serialize_row(row) == row

    def test_rows_to_csv_empty(self):
        assert _rows_to_csv([]) == ""

    def test_rows_to_csv_basic(self):
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        csv_str = _rows_to_csv(rows)
        lines = csv_str.strip().split("\n")
        assert lines[0] == "a,b"
        assert lines[1] == "1,2"
        assert lines[2] == "3,4"


# --- Export trades ---


class TestExportTrades:
    def test_export_trades_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [SAMPLE_TRADE]

        resp = tc.get("/export/trades?format=json")
        assert resp.status_code == 200
        body = resp.json()
        trades = body["data"]["attributes"]["trades"]
        assert len(trades) == 1
        assert trades[0]["symbol"] == "BTC/USD"
        assert trades[0]["pnl"] == 1000.0

    def test_export_trades_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [SAMPLE_TRADE]

        resp = tc.get("/export/trades?format=csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        content = resp.text
        assert "symbol" in content
        assert "BTC/USD" in content

    def test_export_trades_default_json(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/export/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["count"] == 0

    def test_export_trades_with_date_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [SAMPLE_TRADE]

        resp = tc.get(
            "/export/trades?format=json&start_date=2026-01-01&end_date=2026-01-31"
        )
        assert resp.status_code == 200

    def test_export_trades_with_strategy_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get(
            "/export/trades?format=json"
            "&strategy_id=00000000-0000-0000-0000-000000000099"
        )
        assert resp.status_code == 200

    def test_export_trades_invalid_format(self, client):
        tc, conn = client
        resp = tc.get("/export/trades?format=xml")
        assert resp.status_code == 422


# --- Export portfolio ---


class TestExportPortfolio:
    def test_export_portfolio_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [SAMPLE_POSITION]

        resp = tc.get("/export/portfolio?format=json")
        assert resp.status_code == 200
        body = resp.json()
        positions = body["data"]["attributes"]["positions"]
        assert len(positions) == 1
        assert positions[0]["symbol"] == "ETH/USD"
        assert positions[0]["unrealized_pnl"] == 500.0

    def test_export_portfolio_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [SAMPLE_POSITION]

        resp = tc.get("/export/portfolio?format=csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "ETH/USD" in resp.text

    def test_export_portfolio_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/export/portfolio?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["count"] == 0


# --- Performance report ---


class TestPerformanceReport:
    def _setup_report_mocks(self, conn, trades=None, equity=None):
        """Set up the three DB calls: stats, trades, equity curve."""
        stats = FakeRecord(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            total_pnl=5000.0,
            avg_pnl=500.0,
            best_trade=2000.0,
            worst_trade=-500.0,
        )
        if trades is None:
            trades = [SAMPLE_TRADE]
        if equity is None:
            equity = [
                FakeRecord(
                    trade_date=date(2026, 1, 15),
                    cumulative_pnl=500.0,
                    pnl=500.0,
                ),
                FakeRecord(
                    trade_date=date(2026, 1, 18),
                    cumulative_pnl=300.0,
                    pnl=-200.0,
                ),
                FakeRecord(
                    trade_date=date(2026, 1, 20),
                    cumulative_pnl=1000.0,
                    pnl=700.0,
                ),
            ]
        conn.fetchrow.return_value = stats
        conn.fetch.side_effect = [trades, equity]

    def test_basic_report(self, client):
        tc, conn = client
        self._setup_report_mocks(conn)

        resp = tc.post(
            "/reports/performance",
            json={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]

        assert attrs["summary"]["total_trades"] == 10
        assert attrs["summary"]["win_rate"] == 0.7
        assert attrs["summary"]["total_pnl"] == 5000.0
        assert len(attrs["trade_log"]) == 1
        assert len(attrs["equity_curve"]) == 3
        assert attrs["period"]["start_date"] == "2026-01-01"

    def test_report_drawdown(self, client):
        tc, conn = client
        self._setup_report_mocks(conn)

        resp = tc.post(
            "/reports/performance",
            json={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        body = resp.json()
        dd = body["data"]["attributes"]["drawdown"]
        assert dd["max_drawdown"] == 200.0
        assert dd["max_drawdown_pct"] == 0.4

    def test_report_with_strategy_filter(self, client):
        tc, conn = client
        self._setup_report_mocks(conn)

        resp = tc.post(
            "/reports/performance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "strategy_id": "00000000-0000-0000-0000-000000000099",
            },
        )
        assert resp.status_code == 200

    def test_report_invalid_date_range(self, client):
        tc, conn = client
        resp = tc.post(
            "/reports/performance",
            json={"start_date": "2026-02-01", "end_date": "2026-01-01"},
        )
        assert resp.status_code == 422

    def test_report_empty_data(self, client):
        tc, conn = client
        stats = FakeRecord(
            total_trades=0,
            winning_trades=None,
            losing_trades=None,
            total_pnl=None,
            avg_pnl=None,
            best_trade=None,
            worst_trade=None,
        )
        conn.fetchrow.return_value = stats
        conn.fetch.side_effect = [[], []]

        resp = tc.post(
            "/reports/performance",
            json={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["summary"]["total_trades"] == 0
        assert attrs["summary"]["win_rate"] == 0
        assert attrs["equity_curve"] == []
        assert attrs["drawdown"]["max_drawdown"] == 0.0


# --- Health ---


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
