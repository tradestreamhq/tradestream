"""Tests for the Slippage Analysis REST API."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.slippage_analysis.analyzer import (
    build_report,
    classify_size_bucket,
    compute_slippage_bps,
    compute_summary,
    detect_adverse_patterns,
)
from services.slippage_analysis.app import create_app


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


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


def _trade_record(
    trade_id="t1",
    symbol="BTC/USD",
    side="BUY",
    expected_price=50000.0,
    fill_price=50025.0,
    quantity=0.1,
    filled_at=None,
):
    if filled_at is None:
        filled_at = datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc)
    return FakeRecord(
        trade_id=trade_id,
        symbol=symbol,
        side=side,
        expected_price=expected_price,
        fill_price=fill_price,
        order_size=quantity,
        filled_at=filled_at,
    )


# --- Unit tests for analyzer logic ---


class TestSlippageBps:
    def test_buy_positive_slippage(self):
        # BUY: fill > expected = adverse
        bps = compute_slippage_bps(100.0, 100.50, "BUY")
        assert bps == pytest.approx(50.0)

    def test_sell_positive_slippage(self):
        # SELL: fill < expected = adverse
        bps = compute_slippage_bps(100.0, 99.50, "SELL")
        assert bps == pytest.approx(50.0)

    def test_no_slippage(self):
        bps = compute_slippage_bps(100.0, 100.0, "BUY")
        assert bps == 0.0

    def test_zero_expected(self):
        bps = compute_slippage_bps(0.0, 100.0, "BUY")
        assert bps == 0.0

    def test_favorable_buy(self):
        # BUY: fill < expected = favorable
        bps = compute_slippage_bps(100.0, 99.50, "BUY")
        assert bps == pytest.approx(-50.0)


class TestSizeBucket:
    def test_small(self):
        assert classify_size_bucket(0.01, 50000.0) == "small"

    def test_medium(self):
        assert classify_size_bucket(0.1, 50000.0) == "medium"

    def test_large(self):
        assert classify_size_bucket(1.0, 50000.0) == "large"


class TestComputeSummary:
    def test_empty(self):
        result = compute_summary([])
        assert result["total_trades"] == 0
        assert result["avg_slippage_bps"] == 0.0

    def test_single_record(self):
        records = [
            {
                "slippage_bps": 5.0,
                "expected_price": 100.0,
                "fill_price": 100.05,
                "order_size": 10.0,
            }
        ]
        result = compute_summary(records)
        assert result["total_trades"] == 1
        assert result["avg_slippage_bps"] == 5.0
        assert result["median_slippage_bps"] == 5.0

    def test_multiple_records(self):
        records = [
            {
                "slippage_bps": 3.0,
                "expected_price": 100.0,
                "fill_price": 100.03,
                "order_size": 10.0,
            },
            {
                "slippage_bps": 7.0,
                "expected_price": 100.0,
                "fill_price": 100.07,
                "order_size": 10.0,
            },
        ]
        result = compute_summary(records)
        assert result["total_trades"] == 2
        assert result["avg_slippage_bps"] == 5.0
        assert result["median_slippage_bps"] == 5.0


class TestDetectAdversePatterns:
    def test_no_records(self):
        assert detect_adverse_patterns([]) == []

    def test_market_open_pattern(self):
        # Create trades: 5 at market open with high slippage, 5 off-hours with low
        records = []
        for i in range(5):
            records.append(
                {
                    "slippage_bps": 30.0,
                    "hour_of_day": 9,
                    "size_bucket": "medium",
                    "symbol": "BTC/USD",
                    "expected_price": 100.0,
                    "fill_price": 100.30,
                    "order_size": 10.0,
                }
            )
        for i in range(5):
            records.append(
                {
                    "slippage_bps": 2.0,
                    "hour_of_day": 14,
                    "size_bucket": "medium",
                    "symbol": "BTC/USD",
                    "expected_price": 100.0,
                    "fill_price": 100.02,
                    "order_size": 10.0,
                }
            )

        patterns = detect_adverse_patterns(records)
        types = [p["pattern_type"] for p in patterns]
        assert "market_open_slippage" in types

    def test_size_impact_pattern(self):
        records = []
        for i in range(5):
            records.append(
                {
                    "slippage_bps": 25.0,
                    "hour_of_day": 14,
                    "size_bucket": "large",
                    "symbol": "BTC/USD",
                    "expected_price": 100.0,
                    "fill_price": 100.25,
                    "order_size": 200.0,
                }
            )
        for i in range(5):
            records.append(
                {
                    "slippage_bps": 2.0,
                    "hour_of_day": 14,
                    "size_bucket": "small",
                    "symbol": "BTC/USD",
                    "expected_price": 100.0,
                    "fill_price": 100.02,
                    "order_size": 1.0,
                }
            )

        patterns = detect_adverse_patterns(records)
        types = [p["pattern_type"] for p in patterns]
        assert "size_impact" in types


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestSlippageReport:
    def test_report_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/report")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["summary"]["total_trades"] == 0
        assert attrs["by_symbol"] == []
        assert attrs["adverse_patterns"] == []

    def test_report_with_data(self, client):
        tc, conn = client
        filled = datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc)
        conn.fetch.return_value = [
            _trade_record("t1", "BTC/USD", "BUY", 50000.0, 50025.0, 0.1, filled),
            _trade_record("t2", "ETH/USD", "SELL", 3000.0, 2998.5, 1.0, filled),
        ]

        resp = tc.get("/report")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["summary"]["total_trades"] == 2
        assert len(attrs["by_symbol"]) == 2

    def test_report_with_symbol_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/report?symbol=BTC/USD")
        assert resp.status_code == 200


class TestSlippageTrades:
    def test_list_trades_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_list_trades_with_data(self, client):
        tc, conn = client
        filled = datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc)
        conn.fetch.return_value = [
            _trade_record("t1", "BTC/USD", "BUY", 50000.0, 50025.0, 0.1, filled),
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["slippage_bps"] == pytest.approx(5.0)

    def test_list_trades_with_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/trades?limit=10&offset=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 5

    def test_list_trades_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(
            "/trades?symbol=ETH/USD&side=BUY&start_date=2026-01-01&end_date=2026-12-31"
        )
        assert resp.status_code == 200


class TestBuildReport:
    def test_full_report(self):
        records = [
            {
                "trade_id": "t1",
                "symbol": "BTC/USD",
                "side": "BUY",
                "expected_price": 50000.0,
                "fill_price": 50025.0,
                "order_size": 0.1,
                "slippage_bps": 5.0,
                "filled_at": "2026-03-10T14:30:00+00:00",
                "hour_of_day": 14,
                "size_bucket": "medium",
            },
            {
                "trade_id": "t2",
                "symbol": "ETH/USD",
                "side": "SELL",
                "expected_price": 3000.0,
                "fill_price": 2998.5,
                "order_size": 1.0,
                "slippage_bps": 5.0,
                "filled_at": "2026-03-10T15:00:00+00:00",
                "hour_of_day": 15,
                "size_bucket": "medium",
            },
        ]
        report = build_report(records)
        assert report["summary"]["total_trades"] == 2
        assert len(report["by_symbol"]) == 2
        assert len(report["by_hour"]) == 2
        assert len(report["by_size_bucket"]) == 1
