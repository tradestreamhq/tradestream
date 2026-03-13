"""Tests for the Portfolio REST API."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.portfolio_api.app import (
    _serialize_position,
    _update_position_from_trade,
    create_app,
)


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


# ---- Health ----


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# ---- State ----


class TestPortfolioState:
    def test_get_state(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.5,
                avg_entry_price=50000.0,
                unrealized_pnl=1000.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchrow.return_value = FakeRecord(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            total_realized_pnl=5000.0,
        )

        resp = tc.get("/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["position_count"] == 1
        assert body["data"]["attributes"]["positions"][0]["side"] == "LONG"

    def test_get_state_includes_unrealized_sum(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=1.0,
                avg_entry_price=50000.0,
                unrealized_pnl=1000.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            FakeRecord(
                symbol="ETH/USD",
                quantity=10.0,
                avg_entry_price=3000.0,
                unrealized_pnl=-500.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchrow.return_value = FakeRecord(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_realized_pnl=0.0,
        )

        resp = tc.get("/state")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_unrealized_pnl"] == 500.0


# ---- Positions ----


class TestPositions:
    def test_list_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="ETH/USD",
                quantity=10.0,
                avg_entry_price=3000.0,
                unrealized_pnl=500.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/positions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_position_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            symbol="BTC/USD",
            quantity=1.0,
            avg_entry_price=60000.0,
            unrealized_pnl=2000.0,
            side="LONG",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get("/positions/BTC%2FUSD")
        assert resp.status_code == 200

    def test_get_position_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/positions/DOGE%2FUSD")
        assert resp.status_code == 404


class TestCreatePosition:
    def test_create_new_position(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            None,  # No existing position
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.5,
                avg_entry_price=50000.0,
                unrealized_pnl=0.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/positions",
            json={
                "symbol": "BTC/USD",
                "side": "LONG",
                "quantity": 0.5,
                "entry_price": 50000.0,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["quantity"] == 0.5
        assert body["data"]["id"] == "BTC/USD"

    def test_update_existing_same_side(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(
                quantity=1.0,
                avg_entry_price=50000.0,
                side="LONG",
            ),
            FakeRecord(
                symbol="BTC/USD",
                quantity=2.0,
                avg_entry_price=52500.0,
                unrealized_pnl=0.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/positions",
            json={
                "symbol": "BTC/USD",
                "side": "LONG",
                "quantity": 1.0,
                "entry_price": 55000.0,
            },
        )
        assert resp.status_code == 201
        conn.execute.assert_called_once()

    def test_replace_position_different_side(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(
                quantity=1.0,
                avg_entry_price=50000.0,
                side="LONG",
            ),
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.5,
                avg_entry_price=48000.0,
                unrealized_pnl=0.0,
                side="SHORT",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/positions",
            json={
                "symbol": "BTC/USD",
                "side": "SHORT",
                "quantity": 0.5,
                "entry_price": 48000.0,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["side"] == "SHORT"

    def test_create_short_position(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            None,
            FakeRecord(
                symbol="ETH/USD",
                quantity=5.0,
                avg_entry_price=3000.0,
                unrealized_pnl=0.0,
                side="SHORT",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/positions",
            json={
                "symbol": "ETH/USD",
                "side": "SHORT",
                "quantity": 5.0,
                "entry_price": 3000.0,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["attributes"]["side"] == "SHORT"

    def test_invalid_side_rejected(self, client):
        tc, conn = client
        resp = tc.post(
            "/positions",
            json={
                "symbol": "BTC/USD",
                "side": "INVALID",
                "quantity": 1.0,
                "entry_price": 50000.0,
            },
        )
        assert resp.status_code == 422


# ---- Trade event handler ----


class TestTradeEvent:
    def test_buy_trade_creates_long_position(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            None,  # No existing position for _update_position_from_trade
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.1,
                avg_entry_price=50000.0,
                unrealized_pnl=0.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/trades",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "quantity": 0.1,
                "price": 50000.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["trade"]["side"] == "BUY"
        assert attrs["position"]["side"] == "LONG"

    def test_sell_trade_creates_short_position(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            None,  # No existing position
            FakeRecord(
                symbol="ETH/USD",
                quantity=2.0,
                avg_entry_price=3000.0,
                unrealized_pnl=0.0,
                side="SHORT",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/trades",
            json={
                "symbol": "ETH/USD",
                "side": "SELL",
                "quantity": 2.0,
                "price": 3000.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["position"]["side"] == "SHORT"

    def test_trade_with_signal_id(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            None,
            FakeRecord(
                symbol="BTC/USD",
                quantity=0.5,
                avg_entry_price=50000.0,
                unrealized_pnl=0.0,
                side="LONG",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.post(
            "/trades",
            json={
                "symbol": "BTC/USD",
                "side": "BUY",
                "quantity": 0.5,
                "price": 50000.0,
                "signal_id": "abc-123",
            },
        )
        assert resp.status_code == 200
        insert_call = conn.execute.call_args_list[0]
        assert "abc-123" in insert_call.args

    def test_invalid_trade_side_rejected(self, client):
        tc, conn = client
        resp = tc.post(
            "/trades",
            json={
                "symbol": "BTC/USD",
                "side": "HOLD",
                "quantity": 1.0,
                "price": 50000.0,
            },
        )
        assert resp.status_code == 422


# ---- Portfolio history ----


class TestPortfolioHistory:
    def test_get_history(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                snapshot_date=date(2026, 1, 3),
                total_equity=10500.0,
                total_unrealized_pnl=500.0,
                total_realized_pnl=0.0,
                position_count=2,
            ),
            FakeRecord(
                snapshot_date=date(2026, 1, 2),
                total_equity=10200.0,
                total_unrealized_pnl=200.0,
                total_realized_pnl=0.0,
                position_count=2,
            ),
            FakeRecord(
                snapshot_date=date(2026, 1, 1),
                total_equity=10000.0,
                total_unrealized_pnl=0.0,
                total_realized_pnl=0.0,
                position_count=1,
            ),
        ]

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        # Should be in chronological order (reversed from DB DESC)
        assert body["data"][0]["attributes"]["snapshot_date"] == "2026-01-01"
        assert body["data"][-1]["attributes"]["snapshot_date"] == "2026-01-03"

    def test_get_history_with_date_range(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/history?start_date=2026-01-01&end_date=2026-01-31")
        assert resp.status_code == 200
        call_args = conn.fetch.call_args
        assert "2026-01-01" in call_args.args
        assert "2026-01-31" in call_args.args

    def test_get_history_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_get_history_with_limit(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/history?limit=30")
        assert resp.status_code == 200
        call_args = conn.fetch.call_args
        assert 30 in call_args.args


# ---- Snapshot creation ----


class TestSnapshots:
    def test_create_snapshot(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=1.0,
                avg_entry_price=50000.0,
                unrealized_pnl=2000.0,
                side="LONG",
            )
        ]
        conn.fetchrow.return_value = FakeRecord(total_realized=5000.0)

        with patch("services.portfolio_api.app.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 13)
            resp = tc.post("/snapshots")

        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["snapshot_date"] == "2026-03-13"
        assert attrs["total_equity"] == 7000.0
        assert attrs["total_unrealized_pnl"] == 2000.0
        assert attrs["total_realized_pnl"] == 5000.0
        assert attrs["position_count"] == 1

    def test_create_snapshot_empty_portfolio(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchrow.return_value = FakeRecord(total_realized=0.0)

        with patch("services.portfolio_api.app.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 13)
            resp = tc.post("/snapshots")

        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total_equity"] == 0.0
        assert attrs["position_count"] == 0


# ---- Balance ----


class TestBalance:
    def test_get_balance(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(total_unrealized=1500.0),
            FakeRecord(total_realized=3000.0),
        ]

        resp = tc.get("/balance")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_equity"] == 4500.0


# ---- Risk ----


class TestRisk:
    def test_get_risk(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=1.0,
                avg_entry_price=60000.0,
                unrealized_pnl=0.0,
                side="LONG",
            )
        ]

        resp = tc.get("/risk")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["position_count"] == 1
        assert attrs["long_exposure"] == 60000.0
        assert attrs["short_exposure"] == 0.0
        assert attrs["net_exposure"] == 60000.0

    def test_risk_with_long_and_short(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=1.0,
                avg_entry_price=60000.0,
                unrealized_pnl=0.0,
                side="LONG",
            ),
            FakeRecord(
                symbol="ETH/USD",
                quantity=10.0,
                avg_entry_price=3000.0,
                unrealized_pnl=0.0,
                side="SHORT",
            ),
        ]

        resp = tc.get("/risk")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["long_exposure"] == 60000.0
        assert attrs["short_exposure"] == 30000.0
        assert attrs["net_exposure"] == 30000.0
        assert attrs["total_exposure"] == 90000.0


# ---- Validation ----


class TestValidation:
    def test_validate_buy(self, client):
        tc, conn = client
        resp = tc.post(
            "/validate",
            json={"instrument": "BTC/USD", "side": "BUY", "size": 0.1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is True

    def test_validate_sell_insufficient(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(quantity=0.05)

        resp = tc.post(
            "/validate",
            json={"instrument": "BTC/USD", "side": "SELL", "size": 1.0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is False
        assert len(body["data"]["attributes"]["errors"]) > 0


# ---- Helper unit tests ----


class TestSerializePosition:
    def test_serialize_with_timestamp(self):
        row = FakeRecord(
            symbol="BTC/USD",
            quantity=1.0,
            avg_entry_price=50000.0,
            unrealized_pnl=100.0,
            side="LONG",
            updated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        result = _serialize_position(row)
        assert result["quantity"] == 1.0
        assert result["updated_at"] == "2026-01-01T12:00:00+00:00"

    def test_serialize_without_timestamp(self):
        row = FakeRecord(
            symbol="ETH/USD",
            quantity=5.0,
            avg_entry_price=3000.0,
            unrealized_pnl=0.0,
            side="SHORT",
            updated_at=None,
        )
        result = _serialize_position(row)
        assert result["quantity"] == 5.0
        assert result["updated_at"] is None


class TestUpdatePositionFromTrade:
    @pytest.mark.asyncio
    async def test_new_position_buy(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await _update_position_from_trade(conn, "BTC/USD", "BUY", 1.0, 50000.0)

        conn.execute.assert_called_once()
        args = conn.execute.call_args.args
        assert "INSERT" in args[0]
        assert args[4] == "LONG"

    @pytest.mark.asyncio
    async def test_new_position_sell(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = None

        await _update_position_from_trade(
            conn, "BTC/USD", "SELL", 1.0, 50000.0
        )

        args = conn.execute.call_args.args
        assert args[4] == "SHORT"

    @pytest.mark.asyncio
    async def test_increase_long_position(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=1.0, avg_entry_price=50000.0, side="LONG"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "BUY", 1.0, 60000.0
        )

        args = conn.execute.call_args.args
        assert "UPDATE" in args[0]
        assert args[2] == 2.0
        assert args[3] == 55000.0

    @pytest.mark.asyncio
    async def test_partial_close_long(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=2.0, avg_entry_price=50000.0, side="LONG"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "SELL", 1.0, 55000.0
        )

        args = conn.execute.call_args.args
        assert "UPDATE" in args[0]
        assert args[2] == 1.0

    @pytest.mark.asyncio
    async def test_full_close_long(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=1.0, avg_entry_price=50000.0, side="LONG"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "SELL", 1.0, 55000.0
        )

        args = conn.execute.call_args.args
        assert "quantity = 0" in args[0]

    @pytest.mark.asyncio
    async def test_flip_long_to_short(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=1.0, avg_entry_price=50000.0, side="LONG"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "SELL", 2.0, 55000.0
        )

        args = conn.execute.call_args.args
        assert args[2] == 1.0
        assert args[4] == "SHORT"

    @pytest.mark.asyncio
    async def test_increase_short_position(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=1.0, avg_entry_price=50000.0, side="SHORT"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "SELL", 1.0, 48000.0
        )

        args = conn.execute.call_args.args
        assert args[2] == 2.0
        assert args[3] == 49000.0

    @pytest.mark.asyncio
    async def test_partial_close_short(self):
        conn = AsyncMock()
        conn.fetchrow.return_value = FakeRecord(
            quantity=2.0, avg_entry_price=50000.0, side="SHORT"
        )

        await _update_position_from_trade(
            conn, "BTC/USD", "BUY", 1.0, 48000.0
        )

        args = conn.execute.call_args.args
        assert args[2] == 1.0
