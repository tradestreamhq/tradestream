"""Tests for the Data Export and Reporting REST API."""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.export_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    """Create a mock asyncpg pool with async context manager support."""
    pool = AsyncMock()
    conn = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


# --- Health ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "export-api"


# --- Export Trades ---


class TestExportTrades:
    def _trade_row(self, **overrides):
        defaults = dict(
            id=uuid.uuid4(),
            signal_id=uuid.uuid4(),
            symbol="BTC/USD",
            side="BUY",
            entry_price=Decimal("50000.00"),
            exit_price=Decimal("51000.00"),
            quantity=Decimal("0.1"),
            pnl=Decimal("100.00"),
            opened_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            closed_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
            status="CLOSED",
        )
        defaults.update(overrides)
        return FakeRecord(**defaults)

    def test_export_trades_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._trade_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/trades?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["symbol"] == "BTC/USD"

    def test_export_trades_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._trade_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/trades?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "trades.csv" in resp.headers.get("content-disposition", "")

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["symbol"] == "BTC/USD"

    def test_export_trades_with_date_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/trades?start_date=2026-01-01&end_date=2026-01-31")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_export_trades_with_symbol_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._trade_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/trades?symbol=BTC/USD")
        assert resp.status_code == 200

    def test_export_trades_invalid_format(self, client):
        tc, conn = client
        resp = tc.get("/trades?format=xml")
        assert resp.status_code == 422

    def test_export_trades_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._trade_row()]
        conn.fetchval.return_value = 50

        resp = tc.get("/trades?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20
        assert body["meta"]["total"] == 50


# --- Export Signals ---


class TestExportSignals:
    def _signal_row(self, **overrides):
        defaults = dict(
            id=uuid.uuid4(),
            spec_id=uuid.uuid4(),
            implementation_id=uuid.uuid4(),
            instrument="ETH/USD",
            signal_type="BUY",
            strength=Decimal("0.85"),
            price=Decimal("3000.00"),
            stop_loss=Decimal("2900.00"),
            take_profit=Decimal("3200.00"),
            position_size=Decimal("1.0"),
            outcome="PROFIT",
            exit_price=Decimal("3100.00"),
            pnl=Decimal("100.00"),
            pnl_percent=Decimal("3.33"),
            timeframe="1h",
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return FakeRecord(**defaults)

    def test_export_signals_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._signal_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/signals?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["instrument"] == "ETH/USD"

    def test_export_signals_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._signal_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/signals?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_signals_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/signals?instrument=ETH/USD&signal_type=BUY&start_date=2026-01-01")
        assert resp.status_code == 200


# --- Export Performance ---


class TestExportPerformance:
    def _perf_row(self, **overrides):
        defaults = dict(
            id=uuid.uuid4(),
            implementation_id=uuid.uuid4(),
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            sharpe_ratio=Decimal("1.5"),
            sortino_ratio=Decimal("2.0"),
            calmar_ratio=Decimal("1.2"),
            win_rate=Decimal("0.65"),
            profit_factor=Decimal("1.8"),
            max_drawdown=Decimal("-0.12"),
            avg_drawdown=Decimal("-0.05"),
            volatility=Decimal("0.18"),
            var_95=Decimal("-0.03"),
            total_trades=100,
            winning_trades=65,
            losing_trades=35,
            avg_trade_duration_seconds=3600,
            avg_profit_per_trade=Decimal("15.50"),
            total_return=Decimal("0.35"),
            annualized_return=Decimal("0.42"),
            environment="BACKTEST",
            instrument="BTC/USD",
            timeframe="1h",
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return FakeRecord(**defaults)

    def test_export_performance_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._perf_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/performance?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_export_performance_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._perf_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/performance?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_performance_with_filters(self, client):
        tc, conn = client
        impl_id = str(uuid.uuid4())
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(
            f"/performance?implementation_id={impl_id}&environment=BACKTEST&instrument=BTC/USD"
        )
        assert resp.status_code == 200


# --- Export Candles ---


class TestExportCandles:
    def _candle_row(self, **overrides):
        defaults = dict(
            symbol="BTC/USD",
            timeframe="1h",
            timestamp=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
            open=Decimal("50000.00"),
            high=Decimal("50500.00"),
            low=Decimal("49800.00"),
            close=Decimal("50200.00"),
            volume=Decimal("1234.56"),
        )
        defaults.update(overrides)
        return FakeRecord(**defaults)

    def test_export_candles_json(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._candle_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/candles?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["symbol"] == "BTC/USD"

    def test_export_candles_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._candle_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/candles?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


# --- Report: Performance Summary ---


class TestPerformanceSummaryReport:
    def test_performance_summary(self, client):
        tc, conn = client
        impl_id = str(uuid.uuid4())

        perf_rows = [
            FakeRecord(
                period_start=datetime(2026, 1, 1),
                period_end=datetime(2026, 1, 31),
                sharpe_ratio=Decimal("1.5"),
                sortino_ratio=Decimal("2.0"),
                win_rate=Decimal("0.65"),
                profit_factor=Decimal("1.8"),
                max_drawdown=Decimal("-0.12"),
                total_trades=50,
                winning_trades=32,
                losing_trades=18,
                total_return=Decimal("0.25"),
            )
        ]
        signal_rows = [
            FakeRecord(pnl=Decimal("150.00")),
            FakeRecord(pnl=Decimal("-50.00")),
        ]

        conn.fetch.side_effect = [perf_rows, signal_rows]

        resp = tc.get(f"/reports/performance-summary/{impl_id}")
        assert resp.status_code == 200
        body = resp.json()
        report = body["data"]["attributes"]
        assert report["report_type"] == "strategy_performance_summary"
        assert report["summary"]["total_trades"] == 50
        assert report["summary"]["total_pnl"] == 100.0

    def test_performance_summary_not_found(self, client):
        tc, conn = client
        impl_id = str(uuid.uuid4())
        conn.fetch.side_effect = [[], []]

        resp = tc.get(f"/reports/performance-summary/{impl_id}")
        assert resp.status_code == 404


# --- Report: Trade Recap ---


class TestTradeRecapReport:
    def test_trade_recap(self, client):
        tc, conn = client

        signal_rows = [
            FakeRecord(
                id=uuid.uuid4(),
                instrument="BTC/USD",
                signal_type="BUY",
                price=Decimal("50000"),
                exit_price=Decimal("51000"),
                pnl=Decimal("100"),
                outcome="PROFIT",
                created_at=datetime(2026, 3, 1),
            ),
            FakeRecord(
                id=uuid.uuid4(),
                instrument="ETH/USD",
                signal_type="SELL",
                price=Decimal("3000"),
                exit_price=Decimal("3100"),
                pnl=Decimal("-50"),
                outcome="LOSS",
                created_at=datetime(2026, 3, 2),
            ),
        ]
        conn.fetch.return_value = signal_rows

        resp = tc.get(
            "/reports/trade-recap?start_date=2026-03-01&end_date=2026-03-07&period_label=2026-W10"
        )
        assert resp.status_code == 200
        body = resp.json()
        report = body["data"]["attributes"]
        assert report["report_type"] == "trade_recap"
        assert report["period"] == "2026-W10"
        assert report["summary"]["total_signals"] == 2
        assert report["summary"]["wins"] == 1
        assert report["summary"]["losses"] == 1
        assert report["summary"]["total_pnl"] == 50.0


# --- Report: Risk Exposure ---


class TestRiskExposureReport:
    def test_risk_exposure(self, client):
        tc, conn = client

        perf_rows = [
            FakeRecord(
                max_drawdown=Decimal("-0.15"),
                volatility=Decimal("0.22"),
                var_95=Decimal("-0.04"),
            ),
        ]
        open_trades = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=Decimal("0.5"),
                entry_price=Decimal("50000"),
            ),
        ]
        conn.fetch.side_effect = [perf_rows, open_trades]

        resp = tc.get("/reports/risk-exposure")
        assert resp.status_code == 200
        body = resp.json()
        report = body["data"]["attributes"]
        assert report["report_type"] == "risk_exposure"
        assert report["risk_metrics"]["worst_max_drawdown"] == -0.15
        assert report["open_positions"]["position_count"] == 1
        assert report["open_positions"]["total_notional_exposure"] == 25000.0

    def test_risk_exposure_with_implementation_filter(self, client):
        tc, conn = client
        impl_id = str(uuid.uuid4())
        conn.fetch.side_effect = [[], []]

        resp = tc.get(f"/reports/risk-exposure?implementation_id={impl_id}")
        assert resp.status_code == 200


# --- Report Generator Unit Tests ---


class TestReportGeneratorUnit:
    def test_strategy_performance_summary_empty(self):
        from services.export_api.report_generator import strategy_performance_summary

        report = strategy_performance_summary("test-id", [], [])
        assert report["summary"]["total_trades"] == 0
        assert report["summary"]["win_rate"] == 0.0

    def test_trade_recap_no_signals(self):
        from services.export_api.report_generator import trade_recap

        report = trade_recap([], "2026-W10")
        assert report["summary"]["total_signals"] == 0
        assert report["summary"]["win_rate"] == 0.0

    def test_risk_exposure_no_data(self):
        from services.export_api.report_generator import risk_exposure_report

        report = risk_exposure_report([], [])
        assert report["risk_metrics"]["worst_max_drawdown"] is None
        assert report["open_positions"]["position_count"] == 0


# --- Formatters Unit Tests ---


class TestFormatters:
    def test_csv_empty(self):
        from services.export_api.formatters import to_csv_response

        resp = to_csv_response([], "test.csv")
        assert resp.headers.get("content-disposition") == 'attachment; filename="test.csv"'

    def test_csv_with_data(self):
        from services.export_api.formatters import to_csv_response

        rows = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]
        resp = to_csv_response(rows, "test.csv")
        # Read body from StreamingResponse
        body = b"".join(resp.body_iterator).decode()
        reader = csv.DictReader(io.StringIO(body))
        parsed = list(reader)
        assert len(parsed) == 2
        assert parsed[0]["a"] == "1"

    def test_json_export_response(self):
        from services.export_api.formatters import to_json_export_response

        rows = [{"x": 1}]
        resp = to_json_export_response(rows, total=10, limit=5, offset=0)
        body = json.loads(resp.body)
        assert body["meta"]["total"] == 10
        assert body["meta"]["limit"] == 5
