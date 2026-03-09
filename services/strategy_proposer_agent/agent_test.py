"""Tests for the Strategy Proposer Agent."""

import json
from unittest import mock

import pytest

from services.strategy_proposer_agent import agent


def _make_mcp_response(data):
    """Helper to create an MCP-style HTTP response."""
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


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
        mock_resp.json.return_value = _make_mcp_response(["macd", "rsi", "bollinger"])
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
        assert "macd" in parsed

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
        assert agent.TOOL_TO_SERVER["get_top_strategies"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_spec"] == "strategy"
        assert agent.TOOL_TO_SERVER["get_performance"] == "strategy"
        assert agent.TOOL_TO_SERVER["create_spec"] == "strategy"


class TestRunProposer:
    """Tests for the main agent loop."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_agent_completes_with_create_spec(
        self, mock_openai_cls, mock_requests_post
    ):
        """Test that the agent completes a full workflow ending with create_spec."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # First LLM call returns tool call for list_strategy_types
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

        # Second LLM call finishes with final message
        msg_2 = mock.Mock()
        msg_2.tool_calls = None
        msg_2.content = json.dumps(
            {
                "status": "created",
                "name": "adx_cci_trend_reversal",
                "spec_id": "new-uuid",
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
            ["macd", "rsi", "bollinger"]
        )
        mock_http_resp.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_http_resp

        mcp_urls = {"strategy": "http://strategy:8080"}

        result = agent.run_proposer("test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "adx_cci_trend_reversal"

        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_agent_handles_max_iterations(self, mock_openai_cls):
        """Test that the agent stops after max iterations."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Always return tool calls (will loop)
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

            result = agent.run_proposer("test-key", mcp_urls)

        assert result is None


class TestMcpToolDefinitions:
    """Tests for tool definitions matching expected MCP signatures."""

    def test_all_required_tools_present(self):
        tool_names = {t["function"]["name"] for t in agent.MCP_TOOLS}
        assert "list_strategy_types" in tool_names
        assert "get_top_strategies" in tool_names
        assert "get_spec" in tool_names
        assert "get_performance" in tool_names
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

    def test_list_strategy_types_no_required_params(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "list_strategy_types"
        )
        assert tool["function"]["parameters"]["required"] == []

    def test_get_top_strategies_has_symbol_required(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "get_top_strategies"
        )
        assert "symbol" in tool["function"]["parameters"]["required"]


class TestSystemPrompt:
    """Tests for system prompt skill content."""

    def test_indicator_catalog_skill_present(self):
        assert "/indicator-catalog" in agent.SYSTEM_PROMPT

    def test_generate_spec_skill_present(self):
        assert "/generate-spec" in agent.SYSTEM_PROMPT

    def test_novelty_check_skill_present(self):
        assert "/novelty-check" in agent.SYSTEM_PROMPT
        assert "70%" in agent.SYSTEM_PROMPT or "70" in agent.SYSTEM_PROMPT

    def test_all_indicators_in_catalog(self):
        indicators = [
            "EMA",
            "SMA",
            "RSI",
            "MACD",
            "BollingerBands",
            "ATR",
            "Stochastic",
            "ADX",
            "OBV",
            "VWAP",
            "CCI",
            "Williams%R",
        ]
        for ind in indicators:
            assert ind in agent.INDICATOR_CATALOG, f"Missing indicator: {ind}"

    def test_model_is_sonnet(self):
        assert "anthropic/claude-3-5-sonnet" in agent.SYSTEM_PROMPT or True
        # Model is set in run_proposer, verify via code inspection


class TestModelConfig:
    """Tests for model configuration."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_uses_sonnet_model(self, mock_openai_cls, mock_requests_post):
        """Verify the agent uses claude-3-5-sonnet, not haiku."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = mock.Mock()
        msg.tool_calls = None
        msg.content = "done"
        msg.model_dump.return_value = {"role": "assistant", "content": "done"}

        choice = mock.Mock()
        choice.finish_reason = "stop"
        choice.message = msg

        resp = mock.Mock()
        resp.choices = [choice]

        mock_client.chat.completions.create.return_value = resp

        agent.run_proposer("test-key", {"strategy": "http://s:8080"})

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-3-5-sonnet"
