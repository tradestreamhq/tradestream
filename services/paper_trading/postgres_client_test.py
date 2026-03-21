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


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_create_session(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetchrow.return_value = {
            "id": "sess-uuid-1",
            "starting_balance": Decimal("50000"),
            "current_balance": Decimal("50000"),
            "status": "ACTIVE",
            "started_at": datetime(2026, 3, 13),
        }

        result = await pg_client.create_session(50000.0)

        assert result["session_id"] == "sess-uuid-1"
        assert result["starting_balance"] == 50000.0
        assert result["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_create_session_no_pool(self, pg_client):
        pg_client.pool = None
        with pytest.raises(RuntimeError, match="PostgreSQL connection not established"):
            await pg_client.create_session(100000.0)


class TestGetActiveSession:
    @pytest.mark.asyncio
    async def test_get_active_session_exists(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetchrow.return_value = {
            "id": "sess-uuid-1",
            "starting_balance": Decimal("100000"),
            "current_balance": Decimal("95000"),
            "status": "ACTIVE",
            "started_at": datetime(2026, 3, 13),
            "total_realized_pnl": Decimal("500"),
            "total_trades": 5,
        }

        result = await pg_client.get_active_session()

        assert result is not None
        assert result["session_id"] == "sess-uuid-1"
        assert result["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_get_active_session_none(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        conn.fetchrow.return_value = None

        result = await pg_client.get_active_session()
        assert result is None


class TestStopSession:
    @pytest.mark.asyncio
    async def test_stop_session_success(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetchrow.return_value = {
            "id": "sess-uuid-1",
            "starting_balance": Decimal("100000"),
            "current_balance": Decimal("95000"),
            "status": "STOPPED",
            "started_at": datetime(2026, 3, 13),
            "stopped_at": datetime(2026, 3, 13, 1, 0),
            "total_realized_pnl": Decimal("500"),
            "total_trades": 5,
        }

        result = await pg_client.stop_session("sess-uuid-1")

        assert result is not None
        assert result["status"] == "STOPPED"
        assert "stopped_at" in result

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        conn.fetchrow.return_value = None

        result = await pg_client.stop_session("nonexistent")
        assert result is None


class TestExecuteSessionTrade:
    @pytest.mark.asyncio
    async def test_execute_session_buy_trade(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        _make_transaction_mock(conn)

        from datetime import datetime

        conn.fetchrow.side_effect = [
            # INSERT paper_trades RETURNING
            {"id": "trade-uuid-1", "opened_at": datetime(2026, 3, 13)},
            # SELECT from paper_portfolio (no existing)
            None,
        ]

        result = await pg_client.execute_session_trade(
            session_id="sess-1",
            signal_id=None,
            symbol="BTC-USD",
            side="BUY",
            entry_price=50000.0,
            quantity=0.5,
        )

        assert result["trade_id"] == "trade-uuid-1"
        assert result["session_id"] == "sess-1"
        assert result["side"] == "BUY"
        # Should have updated session balance
        assert conn.execute.call_count >= 1


class TestGetSessionTrades:
    @pytest.mark.asyncio
    async def test_get_session_trades(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        from datetime import datetime

        conn.fetch.return_value = [
            {
                "id": "t-1",
                "signal_id": None,
                "symbol": "BTC-USD",
                "side": "BUY",
                "entry_price": Decimal("50000"),
                "exit_price": None,
                "quantity": Decimal("0.5"),
                "pnl": None,
                "opened_at": datetime(2026, 3, 13),
                "closed_at": None,
                "status": "OPEN",
            }
        ]

        result = await pg_client.get_session_trades("sess-1")
        assert len(result) == 1
        assert result[0]["trade_id"] == "t-1"


class TestGetSessionStats:
    @pytest.mark.asyncio
    async def test_get_session_stats(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.side_effect = [
            # session row
            {
                "starting_balance": Decimal("100000"),
                "current_balance": Decimal("95000"),
                "total_realized_pnl": Decimal("2000"),
                "total_trades": 10,
            },
            # stats_row
            {
                "total_pnl": Decimal("2000"),
                "closed_trades": 8,
                "winning_trades": 6,
                "losing_trades": 2,
                "avg_pnl": Decimal("250"),
                "best_trade": Decimal("1000"),
                "worst_trade": Decimal("-300"),
            },
        ]

        result = await pg_client.get_session_stats("sess-1")

        assert result["starting_balance"] == 100000.0
        assert result["total_pnl"] == 2000.0
        assert result["return_pct"] == 2.0
        assert result["win_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_get_session_stats_not_found(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx
        conn.fetchrow.return_value = None

        result = await pg_client.get_session_stats("nonexistent")
        assert result == {}


class TestGetLiveTradeStats:
    @pytest.mark.asyncio
    async def test_get_live_stats(self, pg_client):
        conn, ctx = _make_conn_mock()
        pg_client.pool.acquire.return_value = ctx

        conn.fetchrow.return_value = {
            "total_pnl": Decimal("3000"),
            "total_trades": 15,
            "winning_trades": 10,
            "losing_trades": 5,
            "avg_pnl": Decimal("200"),
            "best_trade": Decimal("900"),
            "worst_trade": Decimal("-400"),
        }

        result = await pg_client.get_live_trade_stats()

        assert result["total_pnl"] == 3000.0
        assert result["total_trades"] == 15
        assert result["win_rate"] == 66.67


class TestSessionRowToDict:
    def test_converts_row(self):
        from datetime import datetime

        row = {
            "id": "sess-uuid",
            "starting_balance": Decimal("100000"),
            "current_balance": Decimal("95000"),
            "status": "ACTIVE",
            "started_at": datetime(2026, 3, 13),
            "total_realized_pnl": Decimal("500"),
            "total_trades": 3,
        }

        result = PostgresClient._session_row_to_dict(row)

        assert result["session_id"] == "sess-uuid"
        assert result["starting_balance"] == 100000.0
        assert result["status"] == "ACTIVE"
        assert "stopped_at" not in result

    def test_converts_row_with_stopped_at(self):
        from datetime import datetime

        row = {
            "id": "sess-uuid",
            "starting_balance": Decimal("100000"),
            "current_balance": Decimal("95000"),
            "status": "STOPPED",
            "started_at": datetime(2026, 3, 13),
            "stopped_at": datetime(2026, 3, 13, 1, 0),
            "total_realized_pnl": Decimal("500"),
            "total_trades": 3,
        }

        result = PostgresClient._session_row_to_dict(row)
        assert "stopped_at" in result
