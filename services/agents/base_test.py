"""Tests for BaseAgent."""

from unittest.mock import MagicMock, patch

import pytest

from services.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    def run(self, **kwargs):
        return {"status": "done", **kwargs}


class TestBaseAgent:
    """Tests for the abstract base agent class."""

    def test_run_must_be_implemented(self):
        with pytest.raises(TypeError):
            BaseAgent("test")  # type: ignore[abstract]

    def test_concrete_agent_run(self):
        agent = ConcreteAgent(
            "test-agent",
            openrouter=MagicMock(),
            mcp=MagicMock(),
        )
        result = agent.run(symbol="BTC-USD")
        assert result == {"status": "done", "symbol": "BTC-USD"}

    def test_agent_name(self):
        agent = ConcreteAgent(
            "my-agent",
            openrouter=MagicMock(),
            mcp=MagicMock(),
        )
        assert agent.name == "my-agent"

    def test_call_mcp_tool_delegates(self):
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {"data": [1, 2, 3]}

        agent = ConcreteAgent(
            "test-agent",
            openrouter=MagicMock(),
            mcp=mock_mcp,
        )
        result = agent.call_mcp_tool("strategy", "get_top_strategies", {"symbol": "BTC-USD"})

        assert result == {"data": [1, 2, 3]}
        mock_mcp.call_tool.assert_called_once_with(
            server="strategy",
            tool_name="get_top_strategies",
            arguments={"symbol": "BTC-USD"},
            timeout=30,
        )

    def test_call_mcp_tool_default_params(self):
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {}

        agent = ConcreteAgent(
            "test-agent",
            openrouter=MagicMock(),
            mcp=mock_mcp,
        )
        agent.call_mcp_tool("market", "get_market_summary")

        mock_mcp.call_tool.assert_called_once_with(
            server="market",
            tool_name="get_market_summary",
            arguments={},
            timeout=30,
        )

    def test_call_mcp_tool_custom_timeout(self):
        mock_mcp = MagicMock()
        mock_mcp.call_tool.return_value = {}

        agent = ConcreteAgent(
            "test-agent",
            openrouter=MagicMock(),
            mcp=mock_mcp,
        )
        agent.call_mcp_tool("signal", "emit_signal", {"action": "BUY"}, timeout=60)

        mock_mcp.call_tool.assert_called_once_with(
            server="signal",
            tool_name="emit_signal",
            arguments={"action": "BUY"},
            timeout=60,
        )

    def test_default_clients_created(self):
        """When no clients are passed, defaults are constructed."""
        with patch("services.agents.base.OpenRouterClient") as mock_or, \
             patch("services.agents.base.MCPClient") as mock_mcp:
            agent = ConcreteAgent("auto-agent", api_key="k", default_model="m")
            mock_or.assert_called_once_with(api_key="k", default_model="m")
            mock_mcp.assert_called_once()
