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
    def audit_recorder(self):
        """Create a mock audit recorder."""
        return AsyncMock()

    @pytest.fixture
    def signal_replayer(self):
        """Create a mock signal replayer."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client, redis_client):
        """Create a signal MCP server instance without audit/replay."""
        return create_server(postgres_client, redis_client)

    @pytest.fixture
    def full_server(self, postgres_client, redis_client, audit_recorder, signal_replayer):
        """Create a signal MCP server instance with audit and replay."""
        return create_server(postgres_client, redis_client, audit_recorder, signal_replayer)

    @pytest.mark.asyncio
    async def test_list_tools(self, full_server):
        """Test that all 8 tools are listed."""
        handlers = full_server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 8

        tool_names = [t.name for t in result.tools]
        assert "emit_signal" in tool_names
        assert "log_decision" in tool_names
        assert "get_recent_signals" in tool_names
        assert "get_paper_pnl" in tool_names
        assert "get_signal_accuracy" in tool_names
        assert "get_audit_log" in tool_names
        assert "replay_signals" in tool_names
        assert "get_replay_result" in tool_names

    @pytest.mark.asyncio
    async def test_emit_signal(self, full_server, postgres_client, redis_client, audit_recorder):
        """Test emit_signal tool records to audit trail."""
        postgres_client.insert_signal.return_value = "test-signal-uuid"

        call_tool_handler = full_server.request_handlers.get("tools/call")
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

        # Verify audit recording
        audit_recorder.record_signal_emitted.assert_called_once_with(
            signal_id="test-signal-uuid",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.85,
            reasoning="Strong bullish momentum",
            strategy_breakdown=[
                {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9},
                {"strategy_type": "RSI", "signal": "BUY", "confidence": 0.8},
            ],
        )

        response = json.loads(result.content[0].text)
        assert response["signal_id"] == "test-signal-uuid"

    @pytest.mark.asyncio
    async def test_emit_signal_without_audit(self, server, postgres_client, redis_client):
        """Test emit_signal works without audit recorder."""
        postgres_client.insert_signal.return_value = "test-signal-uuid"

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "emit_signal"
        request.params.arguments = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "confidence": 0.85,
            "reasoning": "Strong bullish momentum",
            "strategy_breakdown": [],
        }

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert response["signal_id"] == "test-signal-uuid"

    @pytest.mark.asyncio
    async def test_log_decision(self, full_server, postgres_client, audit_recorder):
        """Test log_decision tool records to audit trail."""
        postgres_client.insert_decision.return_value = "test-decision-uuid"

        call_tool_handler = full_server.request_handlers.get("tools/call")
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

        audit_recorder.record_decision_logged.assert_called_once()

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
    async def test_get_audit_log(self, full_server, audit_recorder):
        """Test get_audit_log tool."""
        audit_recorder.get_events.return_value = [
            {
                "id": "audit-1",
                "event_type": "SIGNAL_EMITTED",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "created_at": "2026-03-12T10:00:00",
            }
        ]

        call_tool_handler = full_server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_audit_log"
        request.params.arguments = {"symbol": "BTC/USD", "limit": 50}

        result = await call_tool_handler(request)

        audit_recorder.get_events.assert_called_once()
        response = json.loads(result.content[0].text)
        assert len(response) == 1
        assert response[0]["event_type"] == "SIGNAL_EMITTED"

    @pytest.mark.asyncio
    async def test_get_audit_log_not_configured(self, server):
        """Test get_audit_log returns error when no audit recorder."""
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_audit_log"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "error" in response

    @pytest.mark.asyncio
    async def test_replay_signals(self, full_server, signal_replayer):
        """Test replay_signals tool."""
        mock_summary = MagicMock()
        mock_summary.to_dict.return_value = {
            "replay_group_id": "group-1",
            "total_events": 5,
            "matches": 4,
            "mismatches": 1,
            "match_rate": 80.0,
        }
        signal_replayer.replay.return_value = mock_summary

        call_tool_handler = full_server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "replay_signals"
        request.params.arguments = {
            "start_time": "2026-03-12T00:00:00",
            "end_time": "2026-03-12T12:00:00",
            "symbol": "BTC/USD",
        }

        result = await call_tool_handler(request)

        signal_replayer.replay.assert_called_once()
        response = json.loads(result.content[0].text)
        assert response["total_events"] == 5
        assert response["match_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_replay_signals_not_configured(self, server):
        """Test replay_signals returns error when no replayer."""
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "replay_signals"
        request.params.arguments = {
            "start_time": "2026-03-12T00:00:00",
            "end_time": "2026-03-12T12:00:00",
        }

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "error" in response

    @pytest.mark.asyncio
    async def test_get_replay_result(self, full_server, signal_replayer):
        """Test get_replay_result tool."""
        signal_replayer.get_replay_summary.return_value = {
            "total_events": 10,
            "match_rate": 90.0,
        }

        call_tool_handler = full_server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_replay_result"
        request.params.arguments = {"replay_group_id": "group-123"}

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert response["total_events"] == 10
        assert response["match_rate"] == 90.0

    @pytest.mark.asyncio
    async def test_get_replay_result_not_found(self, full_server, signal_replayer):
        """Test get_replay_result when session not found."""
        signal_replayer.get_replay_summary.return_value = None

        call_tool_handler = full_server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_replay_result"
        request.params.arguments = {"replay_group_id": "nonexistent"}

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "error" in response

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
