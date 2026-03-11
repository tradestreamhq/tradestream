"""Integration tests for the Strategy Proposer Agent LLM loop.

Verifies the full decision pipeline: input → multi-step LLM calls → tool
execution → response parsing → final action.  All LLM and MCP calls are
mocked so no external services are required.
"""

import json
from unittest import mock

import pytest

from services.strategy_proposer_agent import agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_response(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _strategy_types():
    return ["momentum", "mean_reversion", "breakout", "trend_following", "rsi_oversold"]


def _top_strategies(count=5, min_score=0.0):
    strats = [
        {"impl_id": f"impl_{i}", "strategy_type": f"type_{i}", "score": 90 - i * 5}
        for i in range(count)
    ]
    return [s for s in strats if s["score"] >= min_score]


def _performance_data():
    return {
        "sharpe_ratio": 1.8,
        "total_return": 0.42,
        "max_drawdown": -0.15,
        "win_rate": 0.58,
    }


def _created_spec():
    return {"id": "new-spec-uuid", "name": "adx_cci_trend", "status": "created"}


def _mock_tool_call(call_id, name, arguments):
    tc = mock.Mock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _mock_assistant_with_tools(tool_calls):
    """Return (message, choice, response) mocks for a tool-calling turn."""
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
    choice = mock.Mock()
    choice.finish_reason = "tool_calls"
    choice.message = msg
    resp = mock.Mock()
    resp.choices = [choice]
    return resp


def _mock_assistant_stop(content):
    """Return response mock for a final (stop) turn."""
    msg = mock.Mock()
    msg.tool_calls = None
    msg.content = content if isinstance(content, str) else json.dumps(content)
    msg.model_dump.return_value = {"role": "assistant", "content": msg.content}
    choice = mock.Mock()
    choice.finish_reason = "stop"
    choice.message = msg
    resp = mock.Mock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Multi-step workflow tests
# ---------------------------------------------------------------------------


class TestProposerMultiStepWorkflow:
    """Test the full multi-step LLM loop for strategy proposal."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_full_workflow_list_top_create(self, mock_openai_cls, mock_http):
        """Verify a 3-step loop: list_strategy_types → get_top_strategies → create_spec."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Step 1: LLM calls list_strategy_types
        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1", "list_strategy_types", {}),
            ]
        )

        # Step 2: LLM calls get_top_strategies
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc2", "get_top_strategies", {"symbol": "BTC-USD", "limit": 5}
                ),
            ]
        )

        # Step 3: LLM calls create_spec
        spec_args = {
            "name": "adx_cci_trend",
            "indicators": {"ADX": {"period": 14}, "CCI": {"period": 20}},
            "entry_conditions": {"long": "ADX > 25 AND CCI crosses above 0"},
            "exit_conditions": {
                "stop_loss": "price drops 2% from entry",
                "take_profit": "CCI > 100",
            },
            "parameters": {"adx_period": 14, "cci_period": 20},
            "description": "Trend strategy using ADX for strength and CCI for momentum",
        }
        resp3 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc3", "create_spec", spec_args),
            ]
        )

        # Step 4: LLM produces final response
        final_content = {
            "name": "adx_cci_trend",
            "indicators": {"ADX": {"period": 14}, "CCI": {"period": 20}},
            "entry_conditions": {"long": "ADX > 25 AND CCI crosses above 0"},
            "exit_conditions": {
                "stop_loss": "price drops 2% from entry",
                "take_profit": "CCI > 100",
            },
            "parameters": {"adx_period": 14, "cci_period": 20},
            "description": "Trend strategy using ADX for strength and CCI for momentum",
            "status": "created",
        }
        resp4 = _mock_assistant_stop(final_content)

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3, resp4]

        # MCP responses keyed by tool name
        mcp_responses = {
            "list_strategy_types": _make_mcp_response(_strategy_types()),
            "get_top_strategies": _make_mcp_response(_top_strategies()),
            "create_spec": _make_mcp_response(_created_spec()),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = mcp_responses[tool_name]
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent.run_proposer_agent("test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "adx_cci_trend"
        assert "indicators" in parsed
        assert "entry_conditions" in parsed

        # Verify 4 LLM calls were made
        assert mock_client.chat.completions.create.call_count == 4
        # Verify 3 MCP calls were made
        assert mock_http.call_count == 3

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_workflow_with_performance_lookup(self, mock_openai_cls, mock_http):
        """Verify the loop handles an extra get_performance step."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1", "list_strategy_types", {}),
            ]
        )
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc2",
                    "get_top_strategies",
                    {"symbol": "BTC-USD", "limit": 100, "min_score": -999.0},
                ),
            ]
        )
        resp3 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc3", "get_performance", {"impl_id": "impl_0"}),
            ]
        )
        resp4 = _mock_assistant_stop(
            {
                "name": "ema_obv_volume_trend",
                "indicators": {"EMA": {"period": 50}, "OBV": {}},
                "entry_conditions": {"long": "OBV rising AND price > EMA(50)"},
                "exit_conditions": {
                    "stop_loss": "price < EMA(50)",
                    "take_profit": "OBV divergence",
                },
                "parameters": {"ema_period": 50},
                "description": "Volume-confirmed trend following",
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3, resp4]

        mcp_responses = {
            "list_strategy_types": _make_mcp_response(_strategy_types()),
            "get_top_strategies": _make_mcp_response(
                _top_strategies(count=10, min_score=-999)
            ),
            "get_performance": _make_mcp_response(_performance_data()),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = mcp_responses[tool_name]
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect
        mcp_urls = {"strategy": "http://strategy:8080"}

        result = agent.run_proposer_agent("test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "ema_obv_volume_trend"
        assert mock_client.chat.completions.create.call_count == 4


class TestProposerMessageHistory:
    """Verify that message history is built correctly across iterations."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_messages_accumulate_tool_results(self, mock_openai_cls, mock_http):
        """Verify tool results are appended to message history between iterations."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        captured_messages = []

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1", "list_strategy_types", {}),
            ]
        )
        resp2 = _mock_assistant_stop(
            {
                "name": "test",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "x", "take_profit": "y"},
                "parameters": {},
                "description": "test",
            }
        )

        def capture_create(**kwargs):
            # Snapshot the messages list at each call
            captured_messages.append(len(kwargs.get("messages", [])))
            return [resp1, resp2][len(captured_messages) - 1]

        mock_client.chat.completions.create.side_effect = capture_create

        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_mcp_response(_strategy_types())
        mock_resp.raise_for_status.return_value = None
        mock_http.return_value = mock_resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        agent.run_proposer_agent("test-key", mcp_urls)

        # First call: system + user = 2 messages
        assert captured_messages[0] == 2
        # Second call: system + user + assistant(tool_calls) + tool_result = 4 messages
        assert captured_messages[1] == 4


class TestProposerErrorHandling:
    """Test error handling within the LLM loop."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_mcp_failure_mid_loop_continues(self, mock_openai_cls, mock_http):
        """When an MCP call fails mid-loop, the error is passed back to the LLM."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1", "list_strategy_types", {}),
            ]
        )
        resp2 = _mock_assistant_stop(
            {
                "name": "fallback",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "x", "take_profit": "y"},
                "parameters": {},
                "description": "fallback",
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        import requests as req_lib

        mock_http.side_effect = req_lib.RequestException("Connection refused")

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent.run_proposer_agent("test-key", mcp_urls)

        # Agent should still produce a result—the error is passed to the LLM
        assert result is not None

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_invalid_tool_arguments_handled(self, mock_openai_cls, mock_http):
        """When LLM sends invalid JSON for tool arguments, empty dict is used."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc = mock.Mock()
        tc.id = "tc1"
        tc.function.name = "list_strategy_types"
        tc.function.arguments = "not valid json {"  # invalid JSON

        msg = mock.Mock()
        msg.tool_calls = [tc]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {"name": "list_strategy_types", "arguments": "{}"},
                    "type": "function",
                }
            ],
        }
        choice = mock.Mock()
        choice.finish_reason = "tool_calls"
        choice.message = msg
        resp1 = mock.Mock()
        resp1.choices = [choice]

        resp2 = _mock_assistant_stop(
            {
                "name": "test",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "x", "take_profit": "y"},
                "parameters": {},
                "description": "test",
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_mcp_response(_strategy_types())
        mock_resp.raise_for_status.return_value = None
        mock_http.return_value = mock_resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent.run_proposer_agent("test-key", mcp_urls)

        # Should complete without raising
        assert result is not None

    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_llm_api_error_propagates(self, mock_openai_cls):
        """An LLM API error should propagate (not silently swallowed)."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        from openai import APIError

        mock_client.chat.completions.create.side_effect = APIError(
            message="Rate limited",
            request=mock.Mock(),
            body=None,
        )

        mcp_urls = {"strategy": "http://strategy:8080"}

        with pytest.raises(APIError):
            agent.run_proposer_agent("test-key", mcp_urls)

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_unknown_tool_from_llm(self, mock_openai_cls, mock_http):
        """If LLM calls a tool not in TOOL_TO_SERVER, error is returned to LLM."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1", "nonexistent_tool", {"foo": "bar"}),
            ]
        )
        resp2 = _mock_assistant_stop(
            {
                "name": "test",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "x", "take_profit": "y"},
                "parameters": {},
                "description": "test",
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        mcp_urls = {"strategy": "http://strategy:8080"}
        result = agent.run_proposer_agent("test-key", mcp_urls)

        # Should complete — the unknown tool error string is sent back to LLM
        assert result is not None


class TestProposerModelConfiguration:
    """Verify correct model and API configuration."""

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_uses_primary_model(self, mock_openai_cls, mock_http):
        """Strategy proposer must use MODEL_PRIMARY for complex reasoning."""
        from services.shared.model_config import MODEL_PRIMARY

        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp = _mock_assistant_stop(
            {
                "name": "x",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "a", "take_profit": "b"},
                "parameters": {},
                "description": "x",
            }
        )
        mock_client.chat.completions.create.return_value = resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        agent.run_proposer_agent("test-key", mcp_urls)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == MODEL_PRIMARY

    @mock.patch("requests.post")
    @mock.patch("services.strategy_proposer_agent.agent.OpenAI")
    def test_uses_json_response_format(self, mock_openai_cls, mock_http):
        """Strategy proposer requests JSON response format."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp = _mock_assistant_stop(
            {
                "name": "x",
                "indicators": {},
                "entry_conditions": {},
                "exit_conditions": {"stop_loss": "a", "take_profit": "b"},
                "parameters": {},
                "description": "x",
            }
        )
        mock_client.chat.completions.create.return_value = resp

        mcp_urls = {"strategy": "http://strategy:8080"}
        agent.run_proposer_agent("test-key", mcp_urls)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}
