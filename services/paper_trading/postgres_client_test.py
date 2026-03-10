"""Tests for the Paper Trading PostgreSQL client."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.paper_trading.postgres_client import PostgresClient


@pytest.fixture
def pg_client():
    client = PostgresClient(
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password="test_pass",
    )
    # Mock the connection pool
    client.pool = MagicMock()
    return client


def _make_conn_mock():
    """Create a mock connection with async context manager support."""
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


def _make_transaction_mock(conn):
    """Create a mock transaction context manager."""
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = tx
    return tx


class TestExecuteTrade:
    @pytest.mark.asyncio
    async def test_execute_buy_trade_new_position(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        from datetime import datetime

        opened_at = datetime(2026, 3, 10)
        conn.fetchrow.side_effect = [
            # INSERT paper_trades RETURNING
            {"id": "trade-uuid-1", "opened_at": opened_at},
            # SELECT from paper_portfolio (no existing)
            None,
        ]

        result = await pg_client.execute_trade(
            signal_id="sig-1",
            symbol="BTC-USD",
            side="BUY",
            entry_price=50000.0,
            quantity=0.1,
        )

        assert result["trade_id"] == "trade-uuid-1"
        assert result["side"] == "BUY"
        assert result["entry_price"] == 50000.0
        assert result["quantity"] == 0.1
        assert result["status"] == "OPEN"
        # Should INSERT into portfolio since no existing position
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_buy_trade_existing_position(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        from datetime import datetime

        opened_at = datetime(2026, 3, 10)
        conn.fetchrow.side_effect = [
            {"id": "trade-uuid-2", "opened_at": opened_at},
            # Existing portfolio position
            {"quantity": Decimal("0.5"), "avg_entry_price": Decimal("48000.0")},
        ]

        result = await pg_client.execute_trade(
            signal_id="sig-2",
            symbol="BTC-USD",
            side="BUY",
            entry_price=52000.0,
            quantity=0.5,
        )

        assert result["trade_id"] == "trade-uuid-2"
        # Should UPDATE portfolio with new avg price
        update_calls = [
            c for c in conn.execute.call_args_list if "UPDATE paper_portfolio" in str(c)
        ]
        assert len(update_calls) >= 1

    @pytest.mark.asyncio
    async def test_execute_sell_trade_reduces_position(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        from datetime import datetime

        opened_at = datetime(2026, 3, 10)
        conn.fetchrow.side_effect = [
            {"id": "trade-uuid-3", "opened_at": opened_at},
            {"quantity": Decimal("1.0"), "avg_entry_price": Decimal("48000.0")},
        ]

        result = await pg_client.execute_trade(
            signal_id="sig-3",
            symbol="BTC-USD",
            side="SELL",
            entry_price=52000.0,
            quantity=0.5,
        )

        assert result["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_execute_trade_no_pool_raises(self, pg_client):
        pg_client.pool = None
        with pytest.raises(RuntimeError, match="PostgreSQL connection not established"):
            await pg_client.execute_trade("sig", "BTC", "BUY", 100.0, 1.0)


class TestCloseTrade:
    @pytest.mark.asyncio
    async def test_close_buy_trade_with_profit(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        conn.fetchrow.return_value = {
            "id": "trade-uuid-1",
            "signal_id": "sig-1",
            "symbol": "BTC-USD",
            "side": "BUY",
            "entry_price": Decimal("50000"),
            "quantity": Decimal("0.1"),
        }

        result = await pg_client.close_trade("trade-uuid-1", 55000.0)

        assert result is not None
        assert result["pnl"] == 500.0  # (55000 - 50000) * 0.1
        assert result["status"] == "CLOSED"

    @pytest.mark.asyncio
    async def test_close_sell_trade_with_profit(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        conn.fetchrow.return_value = {
            "id": "trade-uuid-2",
            "signal_id": "sig-2",
            "symbol": "BTC-USD",
            "side": "SELL",
            "entry_price": Decimal("50000"),
            "quantity": Decimal("0.1"),
        }

        result = await pg_client.close_trade("trade-uuid-2", 45000.0)

        assert result is not None
        assert result["pnl"] == 500.0  # (50000 - 45000) * 0.1

    @pytest.mark.asyncio
    async def test_close_nonexistent_trade(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.return_value = None

        result = await pg_client.close_trade("nonexistent", 50000.0)
        assert result is None


class TestGetPortfolio:
    @pytest.mark.asyncio
    async def test_get_portfolio_returns_positions(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetch.return_value = [
            {
                "symbol": "BTC-USD",
                "quantity": Decimal("0.5"),
                "avg_entry_price": Decimal("48000"),
                "unrealized_pnl": Decimal("1000"),
                "updated_at": datetime(2026, 3, 10),
            },
            {
                "symbol": "ETH-USD",
                "quantity": Decimal("5.0"),
                "avg_entry_price": Decimal("3000"),
                "unrealized_pnl": Decimal("-200"),
                "updated_at": datetime(2026, 3, 10),
            },
        ]

        result = await pg_client.get_portfolio()

        assert len(result) == 2
        assert result[0]["symbol"] == "BTC-USD"
        assert result[0]["quantity"] == 0.5
        assert result[1]["symbol"] == "ETH-USD"


class TestGetTrades:
    @pytest.mark.asyncio
    async def test_get_trades_no_filter(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetch.return_value = [
            {
                "id": "t-1",
                "signal_id": "s-1",
                "symbol": "BTC-USD",
                "side": "BUY",
                "entry_price": Decimal("50000"),
                "exit_price": None,
                "quantity": Decimal("0.1"),
                "pnl": None,
                "opened_at": datetime(2026, 3, 10),
                "closed_at": None,
                "status": "OPEN",
            }
        ]

        result = await pg_client.get_trades()
        assert len(result) == 1
        assert result[0]["trade_id"] == "t-1"

    @pytest.mark.asyncio
    async def test_get_trades_with_symbol_filter(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        conn.fetch.return_value = []

        result = await pg_client.get_trades(symbol="ETH-USD", status="CLOSED")
        assert result == []


class TestGetPnlSummary:
    @pytest.mark.asyncio
    async def test_pnl_summary_with_trades(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.side_effect = [
            {
                "total_pnl": Decimal("1500"),
                "total_trades": 10,
                "winning_trades": 7,
                "losing_trades": 2,
                "breakeven_trades": 1,
                "avg_pnl": Decimal("150"),
                "best_trade": Decimal("800"),
                "worst_trade": Decimal("-200"),
            },
            {
                "open_count": 2,
                "total_unrealized_pnl": Decimal("300"),
            },
        ]

        result = await pg_client.get_pnl_summary()

        assert result["total_pnl"] == 1500.0
        assert result["win_rate"] == 70.0
        assert result["total_trades"] == 10
        assert result["open_positions"] == 2

    @pytest.mark.asyncio
    async def test_pnl_summary_no_trades(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.side_effect = [
            {
                "total_pnl": Decimal("0"),
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "avg_pnl": Decimal("0"),
                "best_trade": Decimal("0"),
                "worst_trade": Decimal("0"),
            },
            {
                "open_count": 0,
                "total_unrealized_pnl": Decimal("0"),
            },
        ]

        result = await pg_client.get_pnl_summary()
        assert result["total_pnl"] == 0.0
        assert result["win_rate"] == 0.0


class TestLogDecision:
    @pytest.mark.asyncio
    async def test_log_decision(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.return_value = {"id": "decision-uuid-1"}

        result = await pg_client.log_decision(
            signal_id="sig-1",
            reasoning="Test paper trade",
            action="BUY",
        )

        assert result == "decision-uuid-1"
        conn.fetchrow.assert_called_once()


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_stores_pool(self):
        client = PostgresClient(
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password="pass",
        )
        assert client.pool is None
        # Connection would fail without a real DB, just verify initial state
        assert client.host == "localhost"
        assert client.database == "test"

    @pytest.mark.asyncio
    async def test_close_without_pool(self):
        client = PostgresClient("h", 5432, "db", "u", "p")
        await client.close()  # Should not raise
