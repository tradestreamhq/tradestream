"""Tests for the Strategy Proposer Agent."""

import json
from unittest import mock

import pytest

from services.strategy_proposer_agent import agent


def _make_mcp_response(data):
    """Helper to create an MCP-style HTTP response."""
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _make_strategy_types():
    return ["momentum_rsi", "mean_reversion_bb", "trend_following_ema"]


def _make_spec():
    return {
        "name": "momentum_rsi",
        "indicators": {"RSI": {"period": 14}, "EMA": {"period": 20}},
        "entry_conditions": {"rsi_oversold": "RSI < 30 AND price > EMA(20)"},
        "exit_conditions": {"rsi_overbought": "RSI > 70"},
        "parameters": {"position_size": 0.1, "stop_loss_pct": 0.02},
        "source": "LLM_GENERATED",
    }


class TestCallMcpTool:
    """Tests for MCP tool dispatching."""

    def test_unknown_tool_returns_error(self):
        result = agent._call_mcp_tool("unknown_tool", {}, {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_missing_server_url_returns_error(self):
        result = agent._call_mcp_tool("list_strategy_types", {}, {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "No URL configured" in parsed["error"]

    @mock.patch("requests.post")
    def test_successful_mcp_call(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_mcp_response(_make_strategy_types())
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent._call_mcp_tool("list_strategy_types", {}, mcp_urls)

        mock_post.assert_called_once_with(
            "http://strategy:8080/call-tool",
            json={"name": "list_strategy_types", "arguments": {}},
            timeout=30,
        )
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert "momentum_rsi" in parsed

    @mock.patch("requests.post")
    def test_mcp_call_http_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Connection refused")

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent._call_mcp_tool("list_strategy_types", {}, mcp_urls)

        parsed = json.loads(result)
        assert "error" in parsed


class TestToolToServerMapping:
    """Tests for tool-to-server routing."""

    def test_strategy_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["list_strategy_types"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_performance"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_top_strategies"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_spec"] == "strategy"
        assert agent.TOOL_TO_SERVER["create_spec"] == "strategy"


class TestRunAgent:
    """Tests for the main agent loop."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_agent_completes_with_spec(self, mock_openai_cls, mock_requests_post):
        """Test that the agent completes a full workflow."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # First LLM call returns tool calls
        tool_call_1 = mock.Mock()
        tool_call_1.id = "tc_1"
        tool_call_1.function.name = "list_strategy_types"
        tool_call_1.function.arguments = json.dumps({})

        msg_1 = mock.Mock()
        msg_1.tool_calls = [tool_call_1]
        msg_1.content = None
        msg_1.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {
                        "name": "list_strategy_types",
                        "arguments": "{}",
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

        # Second LLM call finishes with a result
        msg_2 = mock.Mock()
        msg_2.tool_calls = None
        msg_2.content = json.dumps(
            {
                "name": "adx_cci_volume_trend",
                "indicators": {
                    "ADX": {"period": 14},
                    "CCI": {"period": 20},
                    "OBV": {},
                },
                "entry_conditions": {
                    "trend_strong": "ADX > 25",
                    "cci_oversold": "CCI < -100",
                    "volume_rising": "OBV slope > 0",
                },
                "exit_conditions": {
                    "cci_overbought": "CCI > 100",
                    "trend_weakening": "ADX < 20",
                },
                "parameters": {"position_size": 0.1, "stop_loss_pct": 0.03},
                "description": "Trend strength + cyclical momentum with volume confirmation",
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
        mock_http_resp.json.return_value = _make_mcp_response(_make_strategy_types())
        mock_http_resp.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_http_resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
        }

        result = agent.run_agent("test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "adx_cci_volume_trend"
        assert "ADX" in parsed["indicators"]

        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_agent_handles_max_iterations(self, mock_openai_cls):
        """Test that the agent stops after max iterations."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tool_call = mock.Mock()
        tool_call.id = "tc_loop"
        tool_call.function.name = "list_strategy_types"
        tool_call.function.arguments = json.dumps({})

        msg = mock.Mock()
        msg.tool_calls = [tool_call]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_loop",
                    "function": {
                        "name": "list_strategy_types",
                        "arguments": "{}",
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
            mock_http.json.return_value = _make_mcp_response([])
            mock_http.raise_for_status.return_value = None
            mock_post.return_value = mock_http

            result = agent.run_agent("test-key", mcp_urls)

        assert result is None


class TestMcpToolDefinitions:
    """Tests for tool definitions matching expected MCP signatures."""

    def test_all_required_tools_present(self):
        tool_names = {t["function"]["name"] for t in agent.MCP_TOOLS}
        assert "list_strategy_types" in tool_names
        assert "get_performance" in tool_names
        assert "get_top_strategies" in tool_names
        assert "get_spec" in tool_names
        assert "create_spec" in tool_names

    def test_create_spec_has_required_params(self):
        create_tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "create_spec"
        )
        required = create_tool["function"]["parameters"]["required"]
        assert "name" in required
        assert "indicators" in required
        assert "entry_conditions" in required
        assert "exit_conditions" in required
        assert "parameters" in required
        assert "description" in required

    def test_get_performance_has_impl_id_required(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "get_performance"
        )
        assert "impl_id" in tool["function"]["parameters"]["required"]


class TestSystemPrompt:
    """Tests for system prompt skill content."""

    def test_indicator_catalog_skill_present(self):
        assert "/indicator-catalog" in agent.SYSTEM_PROMPT
        assert "EMA" in agent.SYSTEM_PROMPT
        assert "RSI" in agent.SYSTEM_PROMPT
        assert "MACD" in agent.SYSTEM_PROMPT
        assert "BollingerBands" in agent.SYSTEM_PROMPT
        assert "ATR" in agent.SYSTEM_PROMPT
        assert "Stochastic" in agent.SYSTEM_PROMPT
        assert "ADX" in agent.SYSTEM_PROMPT
        assert "OBV" in agent.SYSTEM_PROMPT
        assert "VWAP" in agent.SYSTEM_PROMPT
        assert "CCI" in agent.SYSTEM_PROMPT
        assert "Williams%R" in agent.SYSTEM_PROMPT

    def test_generate_spec_skill_present(self):
        assert "/generate-spec" in agent.SYSTEM_PROMPT
        assert "entry_conditions" in agent.SYSTEM_PROMPT
        assert "exit_conditions" in agent.SYSTEM_PROMPT

    def test_novelty_check_skill_present(self):
        assert "/novelty-check" in agent.SYSTEM_PROMPT
        assert "70%" in agent.SYSTEM_PROMPT

    def test_indicator_param_ranges_present(self):
        assert "5-200" in agent.SYSTEM_PROMPT  # EMA/SMA period range
        assert "7-21" in agent.SYSTEM_PROMPT  # RSI period range
        assert "8-15" in agent.SYSTEM_PROMPT  # MACD fast range

    def test_model_uses_sonnet(self):
        """Verify the agent uses Sonnet, not Haiku."""
        # Check in run_agent source that model is claude-3-5-sonnet
        import inspect

        source = inspect.getsource(agent.run_agent)
        assert "claude-3-5-sonnet" in source
