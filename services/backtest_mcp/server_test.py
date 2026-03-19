"""
Tests for the backtest MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.backtest_mcp.server import create_server


class TestBacktestMcpServer:
    """Test cases for the backtest MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a backtest MCP server instance."""
        return create_server(postgres_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 2 tools are listed."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 2

        tool_names = [t.name for t in result.tools]
        assert "run_backtest" in tool_names
        assert "get_historical_performance" in tool_names

    @pytest.mark.asyncio
    async def test_run_backtest(self, server, postgres_client):
        """Test run_backtest tool."""
        postgres_client.run_backtest.return_value = {
            "impl_id": "abc-123",
            "total_return": 0.25,
            "sharpe_ratio": 1.8,
            "max_drawdown": -0.12,
            "win_rate": 0.62,
            "trades": 150,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "run_backtest"
        request.params.arguments = {
            "strategy_id": "abc-123",
            "symbol": "BTC/USD",
        }

        result = await call_tool_handler(request)

        postgres_client.run_backtest.assert_called_once_with(
            strategy_id="abc-123",
            symbol="BTC/USD",
            start_date=None,
            end_date=None,
        )
        response = json.loads(result.content[0].text)
        assert response["sharpe_ratio"] == 1.8
        assert response["trades"] == 150

    @pytest.mark.asyncio
    async def test_run_backtest_with_dates(self, server, postgres_client):
        """Test run_backtest with date range."""
        postgres_client.run_backtest.return_value = {
            "impl_id": "abc-123",
            "total_return": 0.15,
            "sharpe_ratio": 1.2,
            "max_drawdown": -0.08,
            "win_rate": 0.58,
            "trades": 75,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "run_backtest"
        request.params.arguments = {
            "strategy_id": "abc-123",
            "symbol": "ETH/USD",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        }

        result = await call_tool_handler(request)

        postgres_client.run_backtest.assert_called_once_with(
            strategy_id="abc-123",
            symbol="ETH/USD",
            start_date="2025-01-01",
            end_date="2025-12-31",
        )

    @pytest.mark.asyncio
    async def test_get_historical_performance(self, server, postgres_client):
        """Test get_historical_performance tool."""
        postgres_client.get_historical_performance.return_value = {
            "total_signals": 200,
            "accuracy": 0.65,
            "avg_return": 0.003,
            "sharpe": 1.5,
            "period": "3m",
            "environments_available": ["backtest", "paper"],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_historical_performance"
        request.params.arguments = {
            "strategy_id": "abc-123",
            "period": "3m",
        }

        result = await call_tool_handler(request)

        postgres_client.get_historical_performance.assert_called_once_with(
            strategy_id="abc-123",
            symbol=None,
            period="3m",
        )
        response = json.loads(result.content[0].text)
        assert response["total_signals"] == 200
        assert response["sharpe"] == 1.5

    @pytest.mark.asyncio
    async def test_get_historical_performance_defaults(self, server, postgres_client):
        """Test get_historical_performance with default period."""
        postgres_client.get_historical_performance.return_value = {
            "total_signals": 0,
            "accuracy": 0.0,
            "avg_return": 0.0,
            "sharpe": 0.0,
            "period": "3m",
            "environments_available": [],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_historical_performance"
        request.params.arguments = {"strategy_id": "xyz-456"}

        result = await call_tool_handler(request)

        postgres_client.get_historical_performance.assert_called_once_with(
            strategy_id="xyz-456",
            symbol=None,
            period="3m",
        )

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        """Test calling an unknown tool returns error."""
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "nonexistent_tool"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "error" in response
