"""Tests for the Signal Generator Agent."""

import json
import time
from unittest import mock

import pytest

from services.shared.mcp_client import resolve_and_call
from services.signal_generator_agent import agent


def _make_mcp_response(data):
    """Helper to create an MCP-style HTTP response."""
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _make_strategies():
    return [
        {
            "impl_id": "impl_1",
            "strategy_type": "momentum",
            "signal": "BUY",
            "confidence": 0.8,
            "score": 90,
        },
        {
            "impl_id": "impl_2",
            "strategy_type": "mean_reversion",
            "signal": "BUY",
            "confidence": 0.7,
            "score": 85,
        },
        {
            "impl_id": "impl_3",
            "strategy_type": "breakout",
            "signal": "SELL",
            "confidence": 0.6,
            "score": 80,
        },
        {
            "impl_id": "impl_4",
            "strategy_type": "trend_following",
            "signal": "BUY",
            "confidence": 0.75,
            "score": 75,
        },
        {
            "impl_id": "impl_5",
            "strategy_type": "rsi",
            "signal": "BUY",
            "confidence": 0.65,
            "score": 70,
        },
    ]


def _make_market_summary():
    return {
        "symbol": "BTC-USD",
        "price": 50000.0,
        "volume_24h": 1000000,
        "change_24h": 2.5,
    }


def _make_candles(count=50):
    candles = []
    base_price = 50000.0
    for i in range(count):
        candles.append(
            {
                "timestamp": f"2024-01-01T00:{i:02d}:00Z",
                "open": base_price + i * 10,
                "high": base_price + i * 10 + 50,
                "low": base_price + i * 10 - 30,
                "close": base_price + i * 10 + 20,
                "volume": 100 + i,
            }
        )
    return candles


def _make_recent_signals(direction="BUY", minutes_ago=30):
    return [
        {
            "id": "sig_1",
            "symbol": "BTC-USD",
            "action": direction,
            "confidence": 0.8,
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]


class TestCallMcpTool:
    """Tests for MCP tool dispatching."""

    def test_unknown_tool_returns_error(self):
        result = resolve_and_call(
            "unknown_tool", {}, agent.TOOL_TO_SERVER, {}, return_type="string"
        )
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_missing_server_url_returns_error(self):
        result = resolve_and_call(
            "get_top_strategies",
            {"symbol": "BTC-USD"},
            agent.TOOL_TO_SERVER,
            {},
            return_type="string",
        )
        parsed = json.loads(result)
        assert "error" in parsed
        assert "No URL configured" in parsed["error"]

    @mock.patch("requests.post")
    def test_successful_mcp_call(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_mcp_response(
            {"strategies": _make_strategies()}
        )
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = resolve_and_call(
            "get_top_strategies",
            {"symbol": "BTC-USD", "limit": 10},
            agent.TOOL_TO_SERVER,
            mcp_urls,
            return_type="string",
        )

        mock_post.assert_called_once_with(
            "http://strategy:8080/call-tool",
            json={
                "name": "get_top_strategies",
                "arguments": {"symbol": "BTC-USD", "limit": 10},
            },
            timeout=30,
        )
        parsed = json.loads(result)
        assert "strategies" in parsed

    @mock.patch("requests.post")
    def test_mcp_call_http_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Connection refused")

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = resolve_and_call(
            "get_top_strategies",
            {"symbol": "BTC-USD"},
            agent.TOOL_TO_SERVER,
            mcp_urls,
            return_type="string",
        )

        parsed = json.loads(result)
        assert "error" in parsed


class TestToolToServerMapping:
    """Tests for tool-to-server routing."""

    def test_strategy_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["get_top_strategies"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_walk_forward"] == "strategy"

    def test_market_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["get_market_summary"] == "market"
        assert agent.TOOL_TO_SERVER["get_candles"] == "market"

    def test_signal_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["emit_signal"] == "signal"
        assert agent.TOOL_TO_SERVER["get_recent_signals"] == "signal"


class TestRunAgentForSymbol:
    """Tests for the main agent loop."""

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_agent_completes_with_signal(self, mock_openai_cls, mock_requests_post):
        """Test that the agent completes a full workflow."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # First LLM call returns tool calls
        tool_call_1 = mock.Mock()
        tool_call_1.id = "tc_1"
        tool_call_1.function.name = "get_top_strategies"
        tool_call_1.function.arguments = json.dumps({"symbol": "BTC-USD", "limit": 10})

        msg_1 = mock.Mock()
        msg_1.tool_calls = [tool_call_1]
        msg_1.content = None
        msg_1.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {
                        "name": "get_top_strategies",
                        "arguments": '{"symbol":"BTC-USD","limit":10}',
                    },
                    "type": "function",
                }
            ],
        }

        choice_1 = mock.Mock()
        choice_1.finish_reason = "tool_calls"
        choice_1.message = msg_1

        resp_1 = mock.Mock()
        resp_1.choices = [choice_1]

        # Second LLM call finishes
        msg_2 = mock.Mock()
        msg_2.tool_calls = None
        msg_2.content = json.dumps(
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.75,
                "reasoning": "Strong consensus",
                "strategy_breakdown": [
                    {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.8}
                ],
            }
        )
        msg_2.model_dump.return_value = {"role": "assistant", "content": msg_2.content}

        choice_2 = mock.Mock()
        choice_2.finish_reason = "stop"
        choice_2.message = msg_2

        resp_2 = mock.Mock()
        resp_2.choices = [choice_2]

        mock_client.chat.completions.create.side_effect = [resp_1, resp_2]

        # Mock MCP HTTP response
        mock_http_resp = mock.Mock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = _make_mcp_response(
            {"strategies": _make_strategies()}
        )
        mock_http_resp.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_http_resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "BUY"
        assert parsed["confidence"] == 0.75

        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_agent_handles_max_iterations(self, mock_openai_cls):
        """Test that the agent stops after max iterations."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Always return tool calls that need no MCP (will loop)
        tool_call = mock.Mock()
        tool_call.id = "tc_loop"
        tool_call.function.name = "get_top_strategies"
        tool_call.function.arguments = json.dumps({"symbol": "BTC-USD"})

        msg = mock.Mock()
        msg.tool_calls = [tool_call]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_loop",
                    "function": {
                        "name": "get_top_strategies",
                        "arguments": '{"symbol":"BTC-USD"}',
                    },
                    "type": "function",
                }
            ],
        }

        choice = mock.Mock()
        choice.finish_reason = "tool_calls"
        choice.message = msg

        resp = mock.Mock()
        resp.choices = [choice]

        mock_client.chat.completions.create.return_value = resp

        mcp_urls = {"strategy": "http://strategy:8080"}

        with mock.patch("requests.post") as mock_post:
            mock_http = mock.Mock()
            mock_http.status_code = 200
            mock_http.json.return_value = _make_mcp_response({"strategies": []})
            mock_http.raise_for_status.return_value = None
            mock_post.return_value = mock_http

            result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is None


class TestMcpToolDefinitions:
    """Tests for tool definitions matching expected MCP signatures."""

    def test_all_required_tools_present(self):
        tool_names = {t["function"]["name"] for t in agent.MCP_TOOLS}
        assert "get_top_strategies" in tool_names
        assert "get_market_summary" in tool_names
        assert "get_candles" in tool_names
        assert "get_recent_signals" in tool_names
        assert "get_walk_forward" in tool_names
        assert "emit_signal" in tool_names

    def test_emit_signal_has_required_params(self):
        emit_tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "emit_signal"
        )
        required = emit_tool["function"]["parameters"]["required"]
        assert "symbol" in required
        assert "action" in required
        assert "confidence" in required
        assert "reasoning" in required
        assert "strategy_breakdown" in required

    def test_get_top_strategies_has_symbol_required(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "get_top_strategies"
        )
        assert "symbol" in tool["function"]["parameters"]["required"]


class TestSystemPrompt:
    """Tests for system prompt skill content."""

    def test_analyze_consensus_skill_present(self):
        assert "/analyze-consensus" in agent.SYSTEM_PROMPT

    def test_read_market_skill_present(self):
        assert "/read-market" in agent.SYSTEM_PROMPT

    def test_avoid_overfit_skill_present(self):
        assert "/avoid-overfit" in agent.SYSTEM_PROMPT
        assert "sharpe_degradation" in agent.SYSTEM_PROMPT
        assert "0.5" in agent.SYSTEM_PROMPT

    def test_format_signal_skill_present(self):
        assert "/format-signal" in agent.SYSTEM_PROMPT
        assert "15 min" in agent.SYSTEM_PROMPT

    def test_dedup_rule_present(self):
        assert "duplicate" in agent.SYSTEM_PROMPT.lower()
