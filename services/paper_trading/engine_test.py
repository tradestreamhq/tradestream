"""Tests for the Paper Trading Engine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.paper_trading.engine import PaperTradingEngine, _compute_comparison
from services.paper_trading.postgres_client import PostgresClient


@pytest.fixture
def pg_client():
    client = MagicMock(spec=PostgresClient)
    client.create_session = AsyncMock()
    client.get_active_session = AsyncMock()
    client.get_session = AsyncMock()
    client.stop_session = AsyncMock()
    client.execute_session_trade = AsyncMock()
    client.get_session_portfolio = AsyncMock()
    client.get_session_trades = AsyncMock()
    client.get_session_stats = AsyncMock()
    client.get_live_trade_stats = AsyncMock()
    return client


@pytest.fixture
def engine(pg_client):
    return PaperTradingEngine(
        pg_client=pg_client,
        market_mcp_url="http://market-mcp:8080",
    )


class TestStartSession:
    @pytest.mark.asyncio
    async def test_start_session_success(self, engine, pg_client):
        pg_client.get_active_session.return_value = None
        pg_client.create_session.return_value = {
            "session_id": "sess-1",
            "starting_balance": 50000.0,
            "current_balance": 50000.0,
            "status": "ACTIVE",
            "started_at": "2026-03-13T00:00:00",
        }

        result = await engine.start_session(50000.0)

        assert result["session_id"] == "sess-1"
        assert result["starting_balance"] == 50000.0
        pg_client.create_session.assert_called_once_with(50000.0)

    @pytest.mark.asyncio
    async def test_start_session_default_balance(self, engine, pg_client):
        pg_client.get_active_session.return_value = None
        pg_client.create_session.return_value = {
            "session_id": "sess-2",
            "starting_balance": 100000.0,
            "current_balance": 100000.0,
            "status": "ACTIVE",
            "started_at": "2026-03-13T00:00:00",
        }

        result = await engine.start_session()

        pg_client.create_session.assert_called_once_with(100000.0)

    @pytest.mark.asyncio
    async def test_start_session_already_active(self, engine, pg_client):
        pg_client.get_active_session.return_value = {
            "session_id": "existing-sess",
            "status": "ACTIVE",
        }

        with pytest.raises(ValueError, match="already active"):
            await engine.start_session()


class TestStopSession:
    @pytest.mark.asyncio
    async def test_stop_session_success(self, engine, pg_client):
        pg_client.stop_session.return_value = {
            "session_id": "sess-1",
            "status": "STOPPED",
            "stopped_at": "2026-03-13T01:00:00",
        }

        result = await engine.stop_session("sess-1")
        assert result["status"] == "STOPPED"

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, engine, pg_client):
        pg_client.stop_session.return_value = None

        with pytest.raises(ValueError, match="not found or already stopped"):
            await engine.stop_session("nonexistent")


class TestExecutePaperTrade:
    @pytest.mark.asyncio
    @patch.object(PaperTradingEngine, "_get_current_price", return_value=50000.0)
    async def test_execute_buy_trade(self, mock_price, engine, pg_client):
        pg_client.get_session.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "current_balance": 100000.0,
        }
        pg_client.execute_session_trade.return_value = {
            "trade_id": "t-1",
            "session_id": "sess-1",
            "symbol": "BTC-USD",
            "side": "BUY",
            "entry_price": 50000.0,
            "quantity": 0.5,
            "status": "OPEN",
            "opened_at": "2026-03-13T00:00:00",
        }

        result = await engine.execute_paper_trade(
            session_id="sess-1",
            symbol="BTC-USD",
            side="BUY",
            quantity=0.5,
        )

        assert result["trade_id"] == "t-1"
        assert result["side"] == "BUY"
        pg_client.execute_session_trade.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(PaperTradingEngine, "_get_current_price", return_value=50000.0)
    async def test_execute_trade_insufficient_balance(self, mock_price, engine, pg_client):
        pg_client.get_session.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "current_balance": 1000.0,
        }

        with pytest.raises(ValueError, match="Insufficient balance"):
            await engine.execute_paper_trade(
                session_id="sess-1",
                symbol="BTC-USD",
                side="BUY",
                quantity=1.0,
            )

    @pytest.mark.asyncio
    async def test_execute_trade_session_not_found(self, engine, pg_client):
        pg_client.get_session.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await engine.execute_paper_trade(
                session_id="nonexistent",
                symbol="BTC-USD",
                side="BUY",
                quantity=0.1,
            )

    @pytest.mark.asyncio
    async def test_execute_trade_stopped_session(self, engine, pg_client):
        pg_client.get_session.return_value = {
            "session_id": "sess-1",
            "status": "STOPPED",
            "current_balance": 100000.0,
        }

        with pytest.raises(ValueError, match="stopped session"):
            await engine.execute_paper_trade(
                session_id="sess-1",
                symbol="BTC-USD",
                side="BUY",
                quantity=0.1,
            )

    @pytest.mark.asyncio
    @patch.object(PaperTradingEngine, "_get_current_price", return_value=None)
    async def test_execute_trade_price_unavailable(self, mock_price, engine, pg_client):
        pg_client.get_session.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "current_balance": 100000.0,
        }

        with pytest.raises(RuntimeError, match="Could not fetch price"):
            await engine.execute_paper_trade(
                session_id="sess-1",
                symbol="BTC-USD",
                side="BUY",
                quantity=0.1,
            )


class TestGetSessionPortfolio:
    @pytest.mark.asyncio
    @patch.object(PaperTradingEngine, "_get_current_price", return_value=52000.0)
    async def test_get_portfolio_with_positions(self, mock_price, engine, pg_client):
        pg_client.get_session.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "starting_balance": 100000.0,
            "current_balance": 75000.0,
            "total_realized_pnl": 0.0,
        }
        pg_client.get_session_portfolio.return_value = [
            {
                "symbol": "BTC-USD",
                "quantity": 0.5,
                "avg_entry_price": 50000.0,
                "unrealized_pnl": 0.0,
            }
        ]

        result = await engine.get_session_portfolio("sess-1")

        assert result["session_id"] == "sess-1"
        assert result["starting_balance"] == 100000.0
        assert len(result["positions"]) == 1
        assert result["positions"][0]["current_price"] == 52000.0
        assert result["positions"][0]["unrealized_pnl"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_portfolio_session_not_found(self, engine, pg_client):
        pg_client.get_session.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await engine.get_session_portfolio("nonexistent")


class TestGetSessionTrades:
    @pytest.mark.asyncio
    async def test_get_trades(self, engine, pg_client):
        pg_client.get_session_trades.return_value = [
            {"trade_id": "t-1", "symbol": "BTC-USD", "side": "BUY"}
        ]

        result = await engine.get_session_trades("sess-1")

        assert result["session_id"] == "sess-1"
        assert result["count"] == 1
        assert result["trades"][0]["trade_id"] == "t-1"


class TestPerformanceComparison:
    @pytest.mark.asyncio
    async def test_performance_comparison(self, engine, pg_client):
        pg_client.get_session_stats.return_value = {
            "total_pnl": 5000.0,
            "return_pct": 5.0,
            "total_trades": 10,
            "win_rate": 70.0,
            "avg_pnl": 500.0,
        }
        pg_client.get_live_trade_stats.return_value = {
            "total_pnl": 3000.0,
            "return_pct": 3.0,
            "total_trades": 8,
            "win_rate": 62.5,
            "avg_pnl": 375.0,
        }

        result = await engine.get_performance_comparison("sess-1")

        assert result["session_id"] == "sess-1"
        assert result["paper"]["total_pnl"] == 5000.0
        assert result["live"]["total_pnl"] == 3000.0
        assert result["comparison"]["return_pct_delta"] == 2.0
        assert result["comparison"]["win_rate_delta"] == 7.5
        assert result["comparison"]["total_trades_delta"] == 2


class TestComputeComparison:
    def test_compute_positive_delta(self):
        paper = {"return_pct": 10.0, "win_rate": 75.0, "avg_pnl": 200.0, "total_trades": 20}
        live = {"return_pct": 5.0, "win_rate": 60.0, "avg_pnl": 100.0, "total_trades": 15}
        result = _compute_comparison(paper, live)

        assert result["return_pct_delta"] == 5.0
        assert result["win_rate_delta"] == 15.0
        assert result["avg_pnl_delta"] == 100.0
        assert result["total_trades_delta"] == 5

    def test_compute_negative_delta(self):
        paper = {"return_pct": 2.0, "win_rate": 40.0, "avg_pnl": -50.0, "total_trades": 5}
        live = {"return_pct": 8.0, "win_rate": 70.0, "avg_pnl": 150.0, "total_trades": 10}
        result = _compute_comparison(paper, live)

        assert result["return_pct_delta"] == -6.0
        assert result["win_rate_delta"] == -30.0
        assert result["total_trades_delta"] == -5

    def test_compute_empty_stats(self):
        result = _compute_comparison({}, {})
        assert result["return_pct_delta"] == 0.0
        assert result["win_rate_delta"] == 0.0
        assert result["avg_pnl_delta"] == 0.0
        assert result["total_trades_delta"] == 0
