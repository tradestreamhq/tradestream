"""Tests for the Backtest REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.backtest_api.app import create_app


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

    # Transaction context manager
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = txn

    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# --- Health ---


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# --- POST /  (create backtest) ---


class TestCreateBacktest:
    def _candle_rows(self, n=50):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = []
        for i in range(n):
            ts = datetime(2025, 1, 1 + i, tzinfo=timezone.utc) if i < 28 else datetime(
                2025, 2, i - 27, tzinfo=timezone.utc
            )
            price = 100.0 + i
            rows.append(
                FakeRecord(
                    timestamp=ts,
                    open=price * 0.99,
                    high=price * 1.01,
                    low=price * 0.98,
                    close=price,
                    volume=1000.0,
                )
            )
        return rows

    def test_create_backtest_success(self, client):
        tc, conn = client
        conn.fetch.return_value = self._candle_rows()
        conn.execute.return_value = None
        conn.executemany.return_value = None

        resp = tc.post(
            "",
            json={
                "strategy_id": "sma-crossover-1",
                "symbol": "BTC/USD",
                "timeframe": "1d",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-03-01T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "backtest"
        assert body["data"]["id"] is not None
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "COMPLETED"
        assert "total_return" in attrs
        assert "sharpe_ratio" in attrs
        assert "max_drawdown" in attrs
        assert "win_rate" in attrs
        assert "profit_factor" in attrs
        assert "total_trades" in attrs

    def test_create_backtest_invalid_dates(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "strategy_id": "test",
                "symbol": "BTC/USD",
                "timeframe": "1d",
                "start_date": "2025-03-01T00:00:00Z",
                "end_date": "2025-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_create_backtest_no_data(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.post(
            "",
            json={
                "strategy_id": "test",
                "symbol": "UNKNOWN/USD",
                "timeframe": "1d",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-03-01T00:00:00Z",
            },
        )
        assert resp.status_code == 422

    def test_create_backtest_invalid_timeframe(self, client):
        tc, conn = client
        resp = tc.post(
            "",
            json={
                "strategy_id": "test",
                "symbol": "BTC/USD",
                "timeframe": "weekly",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-03-01T00:00:00Z",
            },
        )
        assert resp.status_code == 422


# --- GET /{backtest_id} ---


class TestGetBacktest:
    def test_get_backtest_found(self, client):
        tc, conn = client
        bt_id = uuid.uuid4()

        conn.fetchrow.return_value = FakeRecord(
            id=bt_id,
            strategy_id="sma-1",
            symbol="BTC/USD",
            timeframe="1d",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
            status="COMPLETED",
            total_return=0.15,
            sharpe_ratio=1.2,
            max_drawdown=0.08,
            win_rate=0.6,
            profit_factor=2.1,
            total_trades=10,
            created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )

        # equity curve and trades
        conn.fetch.side_effect = [
            [
                FakeRecord(
                    timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    equity=10000.0,
                    drawdown=0.0,
                ),
                FakeRecord(
                    timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    equity=10150.0,
                    drawdown=0.0,
                ),
            ],
            [
                FakeRecord(
                    side="BUY",
                    entry_time=datetime(2025, 1, 5, tzinfo=timezone.utc),
                    exit_time=datetime(2025, 1, 10, tzinfo=timezone.utc),
                    entry_price=100.0,
                    exit_price=110.0,
                    quantity=1.0,
                    pnl=10.0,
                ),
            ],
        ]

        resp = tc.get(f"/{bt_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == str(bt_id)
        attrs = body["data"]["attributes"]
        assert len(attrs["equity_curve"]) == 2
        assert len(attrs["trades"]) == 1
        assert attrs["total_return"] == 0.15

    def test_get_backtest_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        bt_id = uuid.uuid4()

        resp = tc.get(f"/{bt_id}")
        assert resp.status_code == 404

    def test_get_backtest_invalid_id(self, client):
        tc, conn = client
        resp = tc.get("/not-a-uuid")
        assert resp.status_code == 422


# --- GET / (list backtests) ---


class TestListBacktests:
    def test_list_empty(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_list_with_results(self, client):
        tc, conn = client
        bt_id = uuid.uuid4()
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=bt_id,
                strategy_id="sma-1",
                symbol="BTC/USD",
                timeframe="1d",
                start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
                status="COMPLETED",
                total_return=0.15,
                sharpe_ratio=1.2,
                max_drawdown=0.08,
                win_rate=0.6,
                profit_factor=2.1,
                total_trades=10,
                created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1

    def test_list_with_filters(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("?strategy_id=sma-1&symbol=BTC/USD&status=COMPLETED")
        assert resp.status_code == 200

    def test_list_pagination(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20
