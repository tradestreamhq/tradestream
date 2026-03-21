"""Tests for the Paper Trading service."""

import asyncio
import json
import threading
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.paper_trading.postgres_client import PostgresClient
from services.paper_trading.service import create_app


@pytest.fixture
def pg_client():
    client = MagicMock(spec=PostgresClient)
    client.execute_trade = AsyncMock()
    client.close_trade = AsyncMock()
    client.get_portfolio = AsyncMock()
    client.update_unrealized_pnl = AsyncMock()
    client.get_trades = AsyncMock()
    client.get_pnl_summary = AsyncMock()
    client.log_decision = AsyncMock()
    # Session management methods
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
def event_loop():
    """Provide a background event loop for the test suite."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()


@pytest.fixture
def app(pg_client, event_loop):
    flask_app = create_app(
        pg_client=pg_client,
        market_mcp_url="http://market-mcp:8080",
        signal_mcp_url="http://signal-mcp:8080",
        event_loop=event_loop,
    )
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "paper-trading"


class TestExecuteTradeEndpoint:
    @patch("services.paper_trading.service._get_current_price")
    @patch("services.paper_trading.service.call_mcp_tool")
    def test_execute_buy_trade(self, mock_mcp, mock_price, client, pg_client):
        mock_mcp.return_value = [
            {
                "signal_id": "sig-123",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
            }
        ]
        mock_price.return_value = 50000.0
        pg_client.execute_trade.return_value = {
            "trade_id": "trade-1",
            "signal_id": "sig-123",
            "symbol": "BTC-USD",
            "side": "BUY",
            "entry_price": 50000.0,
            "quantity": 0.1,
            "status": "OPEN",
            "opened_at": "2026-03-10T00:00:00",
        }
        pg_client.log_decision.return_value = "dec-1"

        resp = client.post(
            "/paper/execute",
            json={
                "signal_id": "sig-123",
                "quantity": 0.1,
                "reasoning": "Test trade",
            },
            content_type="application/json",
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["trade_id"] == "trade-1"
        assert data["side"] == "BUY"
        assert data["entry_price"] == 50000.0

        pg_client.execute_trade.assert_called_once()
        pg_client.log_decision.assert_called_once()

    def test_execute_trade_missing_signal_id(self, client):
        resp = client.post(
            "/paper/execute",
            json={"quantity": 0.1},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "signal_id" in resp.get_json()["error"]

    def test_execute_trade_missing_quantity(self, client):
        resp = client.post(
            "/paper/execute",
            json={"signal_id": "sig-123"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "quantity" in resp.get_json()["error"]

    def test_execute_trade_no_body(self, client):
        resp = client.post("/paper/execute")
        assert resp.status_code == 400

    @patch("services.paper_trading.service.call_mcp_tool")
    def test_execute_trade_signal_not_found(self, mock_mcp, client):
        mock_mcp.return_value = []

        resp = client.post(
            "/paper/execute",
            json={"signal_id": "nonexistent", "quantity": 0.1},
            content_type="application/json",
        )
        assert resp.status_code == 404

    @patch("services.paper_trading.service.call_mcp_tool")
    def test_execute_trade_hold_signal_rejected(self, mock_mcp, client):
        mock_mcp.return_value = [
            {
                "signal_id": "sig-hold",
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
            }
        ]

        resp = client.post(
            "/paper/execute",
            json={"signal_id": "sig-hold", "quantity": 0.1},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "HOLD" in resp.get_json()["error"]

    @patch("services.paper_trading.service._get_current_price")
    @patch("services.paper_trading.service.call_mcp_tool")
    def test_execute_trade_price_unavailable(self, mock_mcp, mock_price, client):
        mock_mcp.return_value = [
            {
                "signal_id": "sig-123",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
            }
        ]
        mock_price.return_value = None

        resp = client.post(
            "/paper/execute",
            json={"signal_id": "sig-123", "quantity": 0.1},
            content_type="application/json",
        )
        assert resp.status_code == 502


class TestPortfolioEndpoint:
    @patch("services.paper_trading.service._get_current_price")
    def test_get_portfolio(self, mock_price, client, pg_client):
        pg_client.get_portfolio.return_value = [
            {
                "symbol": "BTC-USD",
                "quantity": 0.5,
                "avg_entry_price": 48000.0,
                "unrealized_pnl": 0.0,
                "updated_at": "2026-03-10T00:00:00",
            }
        ]
        mock_price.return_value = 50000.0

        resp = client.get("/paper/portfolio")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "BTC-USD"
        assert data["positions"][0]["current_price"] == 50000.0
        assert data["positions"][0]["unrealized_pnl"] == 1000.0

    def test_get_portfolio_empty(self, client, pg_client):
        pg_client.get_portfolio.return_value = []

        resp = client.get("/paper/portfolio")
        assert resp.status_code == 200
        assert resp.get_json()["positions"] == []


class TestTradesEndpoint:
    def test_get_trades(self, client, pg_client):
        pg_client.get_trades.return_value = [
            {
                "trade_id": "t-1",
                "signal_id": "s-1",
                "symbol": "BTC-USD",
                "side": "BUY",
                "entry_price": 50000.0,
                "exit_price": None,
                "quantity": 0.1,
                "pnl": None,
                "opened_at": "2026-03-10T00:00:00",
                "closed_at": None,
                "status": "OPEN",
            }
        ]

        resp = client.get("/paper/trades")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["trades"][0]["trade_id"] == "t-1"

    def test_get_trades_with_filters(self, client, pg_client):
        pg_client.get_trades.return_value = []

        resp = client.get("/paper/trades?symbol=ETH-USD&status=CLOSED&limit=10")
        assert resp.status_code == 200
        pg_client.get_trades.assert_called_once_with(
            symbol="ETH-USD", status="CLOSED", limit=10
        )


class TestPnlSummaryEndpoint:
    def test_get_pnl_summary(self, client, pg_client):
        pg_client.get_pnl_summary.return_value = {
            "total_pnl": 1500.0,
            "total_trades": 10,
            "winning_trades": 7,
            "losing_trades": 2,
            "breakeven_trades": 1,
            "win_rate": 70.0,
            "avg_pnl": 150.0,
            "best_trade": 800.0,
            "worst_trade": -200.0,
            "open_positions": 2,
            "total_unrealized_pnl": 300.0,
        }

        resp = client.get("/paper/pnl-summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_pnl"] == 1500.0
        assert data["win_rate"] == 70.0
        assert data["total_trades"] == 10

    def test_get_pnl_summary_with_symbol(self, client, pg_client):
        pg_client.get_pnl_summary.return_value = {
            "total_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "open_positions": 0,
            "total_unrealized_pnl": 0.0,
        }

        resp = client.get("/paper/pnl-summary?symbol=BTC-USD")
        assert resp.status_code == 200
        pg_client.get_pnl_summary.assert_called_once_with(symbol="BTC-USD")


class TestMcpToolCall:
    @patch("requests.post")
    def test_call_mcp_tool_success(self, mock_post):
        from services.shared.mcp_client import call_mcp_tool

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": '{"price": 50000}'}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = call_mcp_tool(
            "get_latest_price",
            {"symbol": "BTC-USD"},
            "http://market:8080",
            timeout=10,
        )
        assert result == {"price": 50000}

    @patch("requests.post")
    def test_call_mcp_tool_failure_returns_error(self, mock_post):
        from services.shared.mcp_client import call_mcp_tool
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Connection refused")
        result = call_mcp_tool("get_latest_price", {}, "http://bad:8080")
        assert "error" in result


class TestGetCurrentPrice:
    @patch("services.paper_trading.service.call_mcp_tool")
    def test_get_price_from_price_field(self, mock_mcp):
        from services.paper_trading.service import _get_current_price

        mock_mcp.return_value = {"price": 50000}
        assert _get_current_price("BTC-USD", "http://market:8080") == 50000.0

    @patch("services.paper_trading.service.call_mcp_tool")
    def test_get_price_from_close_field(self, mock_mcp):
        from services.paper_trading.service import _get_current_price

        mock_mcp.return_value = {"close": 49000}
        assert _get_current_price("BTC-USD", "http://market:8080") == 49000.0

    @patch("services.paper_trading.service.call_mcp_tool")
    def test_get_price_returns_none_on_failure(self, mock_mcp):
        from services.paper_trading.service import _get_current_price

        mock_mcp.return_value = {}
        assert _get_current_price("BTC-USD", "http://market:8080") is None


class TestRunAsyncThreadSafety:
    """Verify that run_async dispatches to a dedicated background event loop."""

    def test_run_async_handles_concurrent_requests(self, client, pg_client):
        """Concurrent requests should safely dispatch to the shared loop."""
        import concurrent.futures

        pg_client.get_pnl_summary.return_value = {
            "total_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "open_positions": 0,
            "total_unrealized_pnl": 0.0,
        }

        def make_request():
            with client.application.test_client() as c:
                return c.get("/paper/pnl-summary").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(make_request) for _ in range(4)]
            results = [f.result() for f in futures]

        assert all(status == 200 for status in results)


class TestStartSessionEndpoint:
    def test_start_session_success(self, client, pg_client):
        pg_client.get_active_session.return_value = None
        pg_client.create_session.return_value = {
            "session_id": "sess-1",
            "starting_balance": 50000.0,
            "current_balance": 50000.0,
            "status": "ACTIVE",
            "started_at": "2026-03-13T00:00:00",
        }

        resp = client.post(
            "/api/v1/paper-trading/start",
            json={"starting_balance": 50000.0},
            content_type="application/json",
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["session_id"] == "sess-1"
        assert data["starting_balance"] == 50000.0

    def test_start_session_default_balance(self, client, pg_client):
        pg_client.get_active_session.return_value = None
        pg_client.create_session.return_value = {
            "session_id": "sess-2",
            "starting_balance": 100000.0,
            "current_balance": 100000.0,
            "status": "ACTIVE",
            "started_at": "2026-03-13T00:00:00",
        }

        resp = client.post("/api/v1/paper-trading/start")
        assert resp.status_code == 201
        assert resp.get_json()["starting_balance"] == 100000.0

    def test_start_session_negative_balance(self, client):
        resp = client.post(
            "/api/v1/paper-trading/start",
            json={"starting_balance": -1000},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "positive" in resp.get_json()["error"]

    def test_start_session_conflict(self, client, pg_client):
        pg_client.get_active_session.return_value = {
            "session_id": "existing",
            "status": "ACTIVE",
        }

        resp = client.post("/api/v1/paper-trading/start")
        assert resp.status_code == 409
        assert "already active" in resp.get_json()["error"]


class TestStopSessionEndpoint:
    def test_stop_session_success(self, client, pg_client):
        pg_client.stop_session.return_value = {
            "session_id": "sess-1",
            "status": "STOPPED",
            "stopped_at": "2026-03-13T01:00:00",
        }

        resp = client.post(
            "/api/v1/paper-trading/stop",
            json={"session_id": "sess-1"},
            content_type="application/json",
        )

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "STOPPED"

    def test_stop_session_missing_id(self, client):
        resp = client.post(
            "/api/v1/paper-trading/stop",
            json={},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_stop_session_not_found(self, client, pg_client):
        pg_client.stop_session.return_value = None

        resp = client.post(
            "/api/v1/paper-trading/stop",
            json={"session_id": "nonexistent"},
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestSessionPortfolioEndpoint:
    @patch("services.paper_trading.engine.PaperTradingEngine._get_current_price")
    def test_get_session_portfolio(self, mock_price, client, pg_client):
        mock_price.return_value = 52000.0
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

        resp = client.get("/api/v1/paper-trading/portfolio?session_id=sess-1")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"] == "sess-1"
        assert len(data["positions"]) == 1
        assert data["positions"][0]["current_price"] == 52000.0

    def test_get_session_portfolio_missing_id(self, client):
        resp = client.get("/api/v1/paper-trading/portfolio")
        assert resp.status_code == 400

    def test_get_session_portfolio_not_found(self, client, pg_client):
        pg_client.get_session.return_value = None

        resp = client.get("/api/v1/paper-trading/portfolio?session_id=nonexistent")
        assert resp.status_code == 404


class TestSessionTradesEndpoint:
    def test_get_session_trades(self, client, pg_client):
        pg_client.get_session_trades.return_value = [
            {"trade_id": "t-1", "symbol": "BTC-USD", "side": "BUY"}
        ]

        resp = client.get("/api/v1/paper-trading/trades?session_id=sess-1")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["trades"][0]["trade_id"] == "t-1"

    def test_get_session_trades_missing_id(self, client):
        resp = client.get("/api/v1/paper-trading/trades")
        assert resp.status_code == 400


class TestPerformanceComparisonEndpoint:
    def test_get_performance(self, client, pg_client):
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

        resp = client.get("/api/v1/paper-trading/performance?session_id=sess-1")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["paper"]["total_pnl"] == 5000.0
        assert data["live"]["total_pnl"] == 3000.0
        assert data["comparison"]["return_pct_delta"] == 2.0

    def test_get_performance_missing_id(self, client):
        resp = client.get("/api/v1/paper-trading/performance")
        assert resp.status_code == 400
