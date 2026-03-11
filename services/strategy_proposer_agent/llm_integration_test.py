"""Integration tests for the Strategy Proposer Agent LLM loop.

Tests the full agent loop with mocked LLM and MCP endpoints, verifying:
- Multi-turn conversation flow with tool calls
- Error handling for LLM API failures
- Token limit / max iteration handling
- Message history accumulation
- Tool call argument parsing and dispatch
"""

import json
from unittest import mock

import pytest

from services.strategy_proposer_agent import agent


def _make_llm_tool_call(tc_id, fn_name, fn_args=None):
    """Create a mock tool call from the LLM."""
    tc = mock.Mock()
    tc.id = tc_id
    tc.function.name = fn_name
    tc.function.arguments = json.dumps(fn_args or {})
    return tc


def _make_llm_response(message, finish_reason="tool_calls"):
    """Create a mock LLM completion response."""
    choice = mock.Mock()
    choice.finish_reason = finish_reason
    choice.message = message
    resp = mock.Mock()
    resp.choices = [choice]
    return resp


def _make_tool_call_message(tool_calls):
    """Create a mock assistant message with tool calls."""
    msg = mock.Mock()
    msg.tool_calls = tool_calls
    msg.content = None
    msg.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
                "type": "function",
            }
            for tc in tool_calls
        ],
    }
    return msg


def _make_final_message(content):
    """Create a mock final assistant message (no tool calls)."""
    msg = mock.Mock()
    msg.tool_calls = None
    msg.content = content
    msg.model_dump.return_value = {"role": "assistant", "content": content}
    return msg


def _make_mcp_http_response(data):
    """Create a mock successful MCP HTTP response."""
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "content": [{"type": "text", "text": json.dumps(data)}]
    }
    resp.raise_for_status.return_value = None
    return resp


_VALID_SPEC = {
    "name": "adx_cci_momentum",
    "indicators": {
        "ADX": {"period": 14},
        "CCI": {"period": 20},
        "EMA": {"period": 50},
    },
    "entry_conditions": {
        "long": "ADX > 25 AND CCI crosses above 0 AND price > EMA(50)"
    },
    "exit_conditions": {
        "stop_loss": "price < EMA(50) - 1.5 * ATR(14)",
        "take_profit": "CCI > 200 OR ADX < 20",
    },
    "parameters": {"adx_period": 14, "cci_period": 20, "ema_period": 50},
    "description": "Momentum strategy using ADX for trend strength and CCI for entry timing",
}

_MCP_URLS = {"strategy": "http://strategy-mcp:8080"}


class TestMultiTurnConversation:
    """Tests for multi-turn LLM conversation with tool calls."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_three_turn_workflow(self, mock_openai_cls, mock_post):
        """Agent: list_strategy_types -> get_top_strategies -> final spec."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: LLM calls list_strategy_types
        tc1 = _make_llm_tool_call("tc_1", "list_strategy_types")
        msg1 = _make_tool_call_message([tc1])
        resp1 = _make_llm_response(msg1)

        # Turn 2: LLM calls get_top_strategies
        tc2 = _make_llm_tool_call(
            "tc_2", "get_top_strategies", {"symbol": "BTC-USD", "limit": 5}
        )
        msg2 = _make_tool_call_message([tc2])
        resp2 = _make_llm_response(msg2)

        # Turn 3: LLM finishes with spec
        msg3 = _make_final_message(json.dumps(_VALID_SPEC))
        resp3 = _make_llm_response(msg3, finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

        # MCP responses
        mock_post.return_value = _make_mcp_http_response(
            ["momentum", "mean_reversion", "breakout"]
        )

        result = agent.run_proposer_agent("test-key", _MCP_URLS)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "adx_cci_momentum"
        assert mock_client.chat.completions.create.call_count == 3

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_parallel_tool_calls_in_single_turn(self, mock_openai_cls, mock_post):
        """LLM issues multiple tool calls in a single turn."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Turn 1: LLM calls two tools at once
        tc1 = _make_llm_tool_call("tc_1", "list_strategy_types")
        tc2 = _make_llm_tool_call(
            "tc_2", "get_top_strategies", {"symbol": "BTC-USD"}
        )
        msg1 = _make_tool_call_message([tc1, tc2])
        resp1 = _make_llm_response(msg1)

        # Turn 2: final
        msg2 = _make_final_message(json.dumps(_VALID_SPEC))
        resp2 = _make_llm_response(msg2, finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_post.return_value = _make_mcp_http_response(["momentum"])

        result = agent.run_proposer_agent("test-key", _MCP_URLS)

        assert result is not None
        # Both tool results should be appended to messages
        assert mock_post.call_count == 2

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_message_history_accumulates(self, mock_openai_cls, mock_post):
        """Verify messages grow with each turn (system + user + assistant + tool)."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc1 = _make_llm_tool_call("tc_1", "list_strategy_types")
        msg1 = _make_tool_call_message([tc1])
        resp1 = _make_llm_response(msg1)

        msg2 = _make_final_message(json.dumps(_VALID_SPEC))
        resp2 = _make_llm_response(msg2, finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_post.return_value = _make_mcp_http_response([])

        agent.run_proposer_agent("test-key", _MCP_URLS)

        calls = mock_client.chat.completions.create.call_args_list
        # First call: system + user = 2 messages
        assert len(calls[0].kwargs["messages"]) == 2
        # Second call: system + user + assistant(tool_call) + tool_result = 4
        assert len(calls[1].kwargs["messages"]) == 4


class TestLlmErrorHandling:
    """Tests for LLM API error handling."""

    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_openai_api_error_propagates(self, mock_openai_cls):
        """An unhandled OpenAI API error should propagate up."""
        from openai import APIError

        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIError(
            message="Rate limit exceeded",
            request=mock.Mock(),
            body=None,
        )

        with pytest.raises(APIError):
            agent.run_proposer_agent("test-key", _MCP_URLS)

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_malformed_tool_args_handled(self, mock_openai_cls, mock_post):
        """LLM returns invalid JSON in tool call arguments."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc1 = mock.Mock()
        tc1.id = "tc_bad"
        tc1.function.name = "list_strategy_types"
        tc1.function.arguments = "not valid json{{"

        msg1 = mock.Mock()
        msg1.tool_calls = [tc1]
        msg1.content = None
        msg1.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_bad",
                    "function": {
                        "name": "list_strategy_types",
                        "arguments": "not valid json{{",
                    },
                    "type": "function",
                }
            ],
        }
        resp1 = _make_llm_response(msg1)

        msg2 = _make_final_message(json.dumps(_VALID_SPEC))
        resp2 = _make_llm_response(msg2, finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_post.return_value = _make_mcp_http_response([])

        # Should not crash - malformed args fallback to {}
        result = agent.run_proposer_agent("test-key", _MCP_URLS)
        assert result is not None

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_mcp_failure_doesnt_crash_loop(self, mock_openai_cls, mock_post):
        """MCP tool returning an error doesn't stop the agent loop."""
        import requests as req_lib

        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc1 = _make_llm_tool_call("tc_1", "list_strategy_types")
        msg1 = _make_tool_call_message([tc1])
        resp1 = _make_llm_response(msg1)

        msg2 = _make_final_message(json.dumps(_VALID_SPEC))
        resp2 = _make_llm_response(msg2, finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        # MCP call fails
        mock_post.side_effect = req_lib.ConnectionError("connection refused")

        result = agent.run_proposer_agent("test-key", _MCP_URLS)
        # Agent should still complete (error is returned as tool result)
        assert result is not None


class TestMaxIterations:
    """Tests for iteration limit behavior."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_returns_none_at_max_iterations(self, mock_openai_cls, mock_post):
        """Agent returns None when max iterations reached without finishing."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc = _make_llm_tool_call("tc_loop", "list_strategy_types")
        msg = _make_tool_call_message([tc])
        resp = _make_llm_response(msg)

        mock_client.chat.completions.create.return_value = resp
        mock_post.return_value = _make_mcp_http_response([])

        result = agent.run_proposer_agent("test-key", _MCP_URLS)

        assert result is None
        assert mock_client.chat.completions.create.call_count == 20

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_finishes_early_on_stop(self, mock_openai_cls, mock_post):
        """Agent exits loop immediately when finish_reason is 'stop'."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = _make_final_message(json.dumps(_VALID_SPEC))
        resp = _make_llm_response(msg, finish_reason="stop")

        mock_client.chat.completions.create.return_value = resp

        result = agent.run_proposer_agent("test-key", _MCP_URLS)

        assert result is not None
        assert mock_client.chat.completions.create.call_count == 1

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_finishes_when_no_tool_calls(self, mock_openai_cls, mock_post):
        """Agent exits when LLM returns no tool_calls (even if finish_reason != stop)."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = _make_final_message(json.dumps(_VALID_SPEC))
        # finish_reason is not "stop" but no tool_calls
        resp = _make_llm_response(msg, finish_reason="length")

        mock_client.chat.completions.create.return_value = resp

        result = agent.run_proposer_agent("test-key", _MCP_URLS)
        assert result is not None
        assert mock_client.chat.completions.create.call_count == 1


class TestOpenAIClientConfiguration:
    """Tests for OpenAI client setup."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_uses_openrouter_base_url(self, mock_openai_cls, mock_post):
        """Client is configured with OpenRouter base URL."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = _make_final_message("{}")
        resp = _make_llm_response(msg, finish_reason="stop")
        mock_client.chat.completions.create.return_value = resp

        agent.run_proposer_agent("my-api-key", _MCP_URLS)

        mock_openai_cls.assert_called_once_with(
            api_key="my-api-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_uses_correct_model(self, mock_openai_cls, mock_post):
        """LLM calls use anthropic/claude-3-5-sonnet model."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = _make_final_message("{}")
        resp = _make_llm_response(msg, finish_reason="stop")
        mock_client.chat.completions.create.return_value = resp

        agent.run_proposer_agent("key", _MCP_URLS)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "anthropic/claude-3-5-sonnet"

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_sends_tools_and_system_prompt(self, mock_openai_cls, mock_post):
        """LLM calls include MCP tools and system prompt."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        msg = _make_final_message("{}")
        resp = _make_llm_response(msg, finish_reason="stop")
        mock_client.chat.completions.create.return_value = resp

        agent.run_proposer_agent("key", _MCP_URLS)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] == agent.MCP_TOOLS
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == agent.SYSTEM_PROMPT
