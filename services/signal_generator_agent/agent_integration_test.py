"""Integration tests for the Signal Generator Agent LLM loop.

Verifies the full decision pipeline: symbol input → multi-step LLM calls
→ tool execution → response parsing → signal emission.  All LLM and MCP
calls are mocked.
"""

import json
from unittest import mock

import pytest

from services.signal_generator_agent import agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_response(data):
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _mock_tool_call(call_id, name, arguments):
    tc = mock.Mock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _mock_assistant_with_tools(tool_calls):
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


def _strategies():
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
    ]


def _market_summary():
    return {
        "symbol": "BTC-USD",
        "price": 50000.0,
        "volume_24h": 1000000,
        "change_24h": 2.5,
    }


def _candles(count=50):
    return [
        {
            "timestamp": f"2024-01-01T00:{i:02d}:00Z",
            "open": 50000 + i * 10,
            "high": 50050 + i * 10,
            "low": 49970 + i * 10,
            "close": 50020 + i * 10,
            "volume": 100 + i,
        }
        for i in range(count)
    ]


def _recent_signals():
    return [
        {
            "id": "sig_old",
            "symbol": "BTC-USD",
            "action": "BUY",
            "confidence": 0.7,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]


def _emit_result():
    return {"signal_id": "sig_new_001", "status": "emitted"}


# ---------------------------------------------------------------------------
# Multi-step workflow tests
# ---------------------------------------------------------------------------


class TestSignalGeneratorMultiStepWorkflow:
    """Test the full multi-step LLM loop for signal generation."""

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_full_workflow_five_steps(self, mock_openai_cls, mock_http):
        """Complete workflow: strategies → market → candles → recent_signals → emit_signal."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # Step 1: get_top_strategies
        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": "BTC-USD", "limit": 10}
                ),
            ]
        )
        # Step 2: get_market_summary + get_candles (two tools in one turn)
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc2a", "get_market_summary", {"symbol": "BTC-USD"}),
                _mock_tool_call(
                    "tc2b", "get_candles", {"symbol": "BTC-USD", "limit": 50}
                ),
            ]
        )
        # Step 3: get_recent_signals
        resp3 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc3", "get_recent_signals", {"symbol": "BTC-USD", "limit": 5}
                ),
            ]
        )
        # Step 4: emit_signal
        resp4 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc4",
                    "emit_signal",
                    {
                        "symbol": "BTC-USD",
                        "action": "BUY",
                        "confidence": 0.78,
                        "reasoning": "Strong momentum consensus with bullish market",
                        "strategy_breakdown": [
                            {
                                "strategy_type": "momentum",
                                "signal": "BUY",
                                "confidence": 0.8,
                            },
                            {
                                "strategy_type": "mean_reversion",
                                "signal": "BUY",
                                "confidence": 0.7,
                            },
                        ],
                    },
                ),
            ]
        )
        # Step 5: Final response
        final_content = {
            "symbol": "BTC-USD",
            "action": "BUY",
            "confidence": 0.78,
            "reasoning": "Strong momentum consensus with bullish market",
            "strategy_breakdown": [
                {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.8},
                {"strategy_type": "mean_reversion", "signal": "BUY", "confidence": 0.7},
            ],
        }
        resp5 = _mock_assistant_stop(final_content)

        mock_client.chat.completions.create.side_effect = [
            resp1,
            resp2,
            resp3,
            resp4,
            resp5,
        ]

        mcp_data = {
            "get_top_strategies": _strategies(),
            "get_market_summary": _market_summary(),
            "get_candles": _candles(),
            "get_recent_signals": _recent_signals(),
            "emit_signal": _emit_result(),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "BUY"
        assert parsed["confidence"] == 0.78
        assert len(parsed["strategy_breakdown"]) == 2

        # 5 LLM calls
        assert mock_client.chat.completions.create.call_count == 5
        # 5 MCP calls (strategies, market, candles, recent_signals, emit)
        assert mock_http.call_count == 5

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_workflow_with_walk_forward_check(self, mock_openai_cls, mock_http):
        """Agent includes walk-forward validation before emitting."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": "BTC-USD", "limit": 10}
                ),
            ]
        )
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc2", "get_walk_forward", {"impl_id": "impl_1"}),
            ]
        )
        resp3 = _mock_assistant_stop(
            {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.4,
                "reasoning": "Walk-forward validation failed for top strategy",
                "strategy_breakdown": [],
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

        mcp_data = {
            "get_top_strategies": _strategies(),
            "get_walk_forward": {
                "validation_status": "FAILED",
                "sharpe_degradation": 0.8,
            },
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_deduplication_skips_emit(self, mock_openai_cls, mock_http):
        """Agent skips emit when a recent duplicate signal exists."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": "BTC-USD", "limit": 10}
                ),
            ]
        )
        resp2 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc2", "get_recent_signals", {"symbol": "BTC-USD", "limit": 5}
                ),
            ]
        )
        # LLM decides to skip due to dedup
        resp3 = _mock_assistant_stop(
            {"skipped": True, "reason": "duplicate signal within 15 minutes"}
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

        mcp_data = {
            "get_top_strategies": _strategies(),
            "get_recent_signals": [
                {
                    "id": "sig_recent",
                    "symbol": "BTC-USD",
                    "action": "BUY",
                    "confidence": 0.8,
                    "created_at": "2026-03-09T11:58:00Z",
                },
            ],
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["skipped"] is True


class TestSignalGeneratorMessageHistory:
    """Verify message history is built correctly across iterations."""

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_multi_tool_turn_appends_all_results(self, mock_openai_cls, mock_http):
        """When LLM requests multiple tools in one turn, all results are appended."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        captured_messages = []

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call("tc1a", "get_market_summary", {"symbol": "BTC-USD"}),
                _mock_tool_call(
                    "tc1b", "get_candles", {"symbol": "BTC-USD", "limit": 50}
                ),
            ]
        )
        resp2 = _mock_assistant_stop(
            {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
                "reasoning": "test",
                "strategy_breakdown": [],
            }
        )

        def capture_create(**kwargs):
            captured_messages.append(len(kwargs.get("messages", [])))
            return [resp1, resp2][len(captured_messages) - 1]

        mock_client.chat.completions.create.side_effect = capture_create

        mcp_data = {
            "get_market_summary": _market_summary(),
            "get_candles": _candles(),
        }

        def http_side_effect(url, json=None, timeout=None):
            tool_name = json["name"]
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = _make_mcp_response(mcp_data[tool_name])
            resp.raise_for_status.return_value = None
            return resp

        mock_http.side_effect = http_side_effect

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        # First call: system + user = 2
        assert captured_messages[0] == 2
        # Second call: system + user + assistant(2 tool_calls) + 2 tool_results = 5
        assert captured_messages[1] == 5


class TestSignalGeneratorErrorHandling:
    """Test error handling within the signal generator LLM loop."""

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_mcp_failure_mid_loop_continues(self, mock_openai_cls, mock_http):
        """MCP failure passes error to LLM; loop continues to next iteration."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp1 = _mock_assistant_with_tools(
            [
                _mock_tool_call(
                    "tc1", "get_top_strategies", {"symbol": "BTC-USD", "limit": 10}
                ),
            ]
        )
        resp2 = _mock_assistant_stop(
            {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.3,
                "reasoning": "Could not fetch strategy data",
                "strategy_breakdown": [],
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        import requests as req_lib

        mock_http.side_effect = req_lib.RequestException("Connection refused")

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_llm_api_error_propagates(self, mock_openai_cls):
        """LLM API errors should propagate."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        from openai import APIError

        mock_client.chat.completions.create.side_effect = APIError(
            message="Rate limited",
            request=mock.Mock(),
            body=None,
        )

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        with pytest.raises(APIError):
            agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_invalid_tool_args_handled(self, mock_openai_cls, mock_http):
        """Invalid JSON in tool arguments falls back to empty dict."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tc = mock.Mock()
        tc.id = "tc1"
        tc.function.name = "get_top_strategies"
        tc.function.arguments = "not valid json"

        msg = mock.Mock()
        msg.tool_calls = [tc]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {"name": "get_top_strategies", "arguments": "{}"},
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
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
                "reasoning": "test",
                "strategy_breakdown": [],
            }
        )

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_mcp_response(_strategies())
        mock_resp.raise_for_status.return_value = None
        mock_http.return_value = mock_resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        assert result is not None


class TestSignalGeneratorModelConfiguration:
    """Verify correct model and configuration."""

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_uses_lightweight_model(self, mock_openai_cls, mock_http):
        """Signal generator must use MODEL_LIGHTWEIGHT for high-volume tasks."""
        from services.shared.model_config import MODEL_LIGHTWEIGHT

        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp = _mock_assistant_stop(
            {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
                "reasoning": "test",
                "strategy_breakdown": [],
            }
        )
        mock_client.chat.completions.create.return_value = resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == MODEL_LIGHTWEIGHT

    @mock.patch("requests.post")
    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_tools_passed_to_llm(self, mock_openai_cls, mock_http):
        """All MCP tools are passed to the LLM."""
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        resp = _mock_assistant_stop(
            {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": 0.5,
                "reasoning": "test",
                "strategy_breakdown": [],
            }
        )
        mock_client.chat.completions.create.return_value = resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        agent.run_agent_for_symbol("BTC-USD", "test-key", mcp_urls)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["tools"] == agent.MCP_TOOLS
        assert call_kwargs.kwargs["tool_choice"] == "auto"
