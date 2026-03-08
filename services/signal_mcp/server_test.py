"""
Tests for the signal MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.signal_mcp.server import create_server


class TestSignalMcpServer:
    """Test cases for the signal MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def server(self, postgres_client, redis_client):
        """Create a signal MCP server instance."""
        return create_server(postgres_client, redis_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 5 tools are listed."""
        # Access the handler directly from the server's request handlers
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 5

        tool_names = [t.name for t in result.tools]
        assert "emit_signal" in tool_names
        assert "log_decision" in tool_names
        assert "get_recent_signals" in tool_names
        assert "get_paper_pnl" in tool_names
        assert "get_signal_accuracy" in tool_names

    @pytest.mark.asyncio
    async def test_emit_signal(self, server, postgres_client, redis_client):
        """Test emit_signal tool."""
        postgres_client.insert_signal.return_value = "test-signal-uuid"

        call_tool_handler = server.request_handlers.get("tools/call")
        assert call_tool_handler is not None

        request = MagicMock()
        request.params.name = "emit_signal"
        request.params.arguments = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "confidence": 0.85,
            "reasoning": "Strong bullish momentum",
            "strategy_breakdown": [
                {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9},
                {"strategy_type": "RSI", "signal": "BUY", "confidence": 0.8},
            ],
        }

        result = await call_tool_handler(request)

        postgres_client.insert_signal.assert_called_once_with(
            symbol="BTC/USD",
            action="BUY",
            confidence=0.85,
            reasoning="Strong bullish momentum",
            strategy_breakdown=[
                {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9},
                {"strategy_type": "RSI", "signal": "BUY", "confidence": 0.8},
            ],
        )
        redis_client.publish_signal.assert_called_once()
        response = json.loads(result.content[0].text)
        assert response["signal_id"] == "test-signal-uuid"

    @pytest.mark.asyncio
    async def test_log_decision(self, server, postgres_client):
        """Test log_decision tool."""
        postgres_client.insert_decision.return_value = "test-decision-uuid"

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "log_decision"
        request.params.arguments = {
            "signal_id": "test-signal-uuid",
            "score": 0.92,
            "tier": "HIGH",
            "reasoning": "High confidence signal with multiple confirmations",
            "tool_calls": [{"name": "get_candles", "args": {"symbol": "BTC/USD"}}],
            "model_used": "claude-opus-4-6",
            "latency_ms": 1500,
            "tokens": 2000,
        }

        result = await call_tool_handler(request)

        postgres_client.insert_decision.assert_called_once_with(
            signal_id="test-signal-uuid",
            score=0.92,
            tier="HIGH",
            reasoning="High confidence signal with multiple confirmations",
            tool_calls=[{"name": "get_candles", "args": {"symbol": "BTC/USD"}}],
            model_used="claude-opus-4-6",
            latency_ms=1500,
            tokens_used=2000,
        )
        response = json.loads(result.content[0].text)
        assert response["decision_id"] == "test-decision-uuid"

    @pytest.mark.asyncio
    async def test_get_recent_signals(self, server, postgres_client):
        """Test get_recent_signals tool."""
        postgres_client.get_recent_signals.return_value = [
            {
                "signal_id": "uuid-1",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "score": 0.92,
                "tier": "HIGH",
                "reasoning": "Bullish",
                "timestamp": "2026-03-08T12:00:00",
            }
        ]

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_recent_signals"
        request.params.arguments = {"symbol": "BTC/USD", "limit": 10}

        result = await call_tool_handler(request)

        postgres_client.get_recent_signals.assert_called_once_with(
            symbol="BTC/USD",
            limit=10,
            min_score=None,
        )
        response = json.loads(result.content[0].text)
        assert len(response) == 1
        assert response[0]["symbol"] == "BTC/USD"

    @pytest.mark.asyncio
    async def test_get_recent_signals_defaults(self, server, postgres_client):
        """Test get_recent_signals with default parameters."""
        postgres_client.get_recent_signals.return_value = []

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_recent_signals"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        postgres_client.get_recent_signals.assert_called_once_with(
            symbol=None,
            limit=20,
            min_score=None,
        )

    @pytest.mark.asyncio
    async def test_get_paper_pnl(self, server, postgres_client):
        """Test get_paper_pnl tool."""
        postgres_client.get_paper_pnl.return_value = {
            "total_pnl": 1500.50,
            "win_rate": 65.0,
            "avg_return": 2.5,
            "open_positions": 3,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_paper_pnl"
        request.params.arguments = {"symbol": "BTC/USD"}

        result = await call_tool_handler(request)

        postgres_client.get_paper_pnl.assert_called_once_with(symbol="BTC/USD")
        response = json.loads(result.content[0].text)
        assert response["total_pnl"] == 1500.50
        assert response["win_rate"] == 65.0

    @pytest.mark.asyncio
    async def test_get_paper_pnl_no_symbol(self, server, postgres_client):
        """Test get_paper_pnl without symbol filter."""
        postgres_client.get_paper_pnl.return_value = {
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "open_positions": 0,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_paper_pnl"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        postgres_client.get_paper_pnl.assert_called_once_with(symbol=None)

    @pytest.mark.asyncio
    async def test_get_signal_accuracy(self, server, postgres_client):
        """Test get_signal_accuracy tool."""
        postgres_client.get_signal_accuracy.return_value = {
            "total": 100,
            "correct": 72,
            "accuracy": 72.0,
            "avg_confidence_correct": 0.88,
            "avg_confidence_incorrect": 0.62,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_signal_accuracy"
        request.params.arguments = {"lookback_hours": 48}

        result = await call_tool_handler(request)

        postgres_client.get_signal_accuracy.assert_called_once_with(
            lookback_hours=48,
        )
        response = json.loads(result.content[0].text)
        assert response["total"] == 100
        assert response["accuracy"] == 72.0

    @pytest.mark.asyncio
    async def test_get_signal_accuracy_defaults(self, server, postgres_client):
        """Test get_signal_accuracy with default lookback."""
        postgres_client.get_signal_accuracy.return_value = {
            "total": 0,
            "correct": 0,
            "accuracy": 0.0,
            "avg_confidence_correct": None,
            "avg_confidence_incorrect": None,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_signal_accuracy"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        postgres_client.get_signal_accuracy.assert_called_once_with(
            lookback_hours=24,
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
