"""Tests for the Signal Generator Agent."""

import json
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest

from services.signal_generator_agent.agent import (
    TOOL_TO_MCP_SERVER,
    _call_mcp_tool,
    compute_consensus,
    generate_signal,
    is_duplicate_signal,
)


@pytest.fixture
def mcp_urls():
    return {
        "strategy": "http://strategy-mcp:8080",
        "market": "http://market-mcp:8080",
        "signal": "http://signal-mcp:8080",
    }


class TestComputeConsensus:
    """Tests for the compute_consensus function."""

    def test_clear_buy_consensus(self):
        strategies = [
            {"signal": "BUY", "confidence": 0.9},
            {"signal": "BUY", "confidence": 0.8},
            {"signal": "BUY", "confidence": 0.7},
            {"signal": "SELL", "confidence": 0.6},
        ]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "BUY"
        assert agree == 3
        assert total == 4
        assert abs(avg_conf - 0.75) < 0.01

    def test_clear_sell_consensus(self):
        strategies = [
            {"signal": "SELL", "confidence": 0.9},
            {"signal": "SELL", "confidence": 0.8},
            {"signal": "BUY", "confidence": 0.5},
        ]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "SELL"
        assert agree == 2
        assert total == 3

    def test_tie_defaults_to_hold(self):
        strategies = [
            {"signal": "BUY", "confidence": 0.9},
            {"signal": "SELL", "confidence": 0.8},
        ]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "HOLD"
        assert total == 2

    def test_three_way_tie_defaults_to_hold(self):
        strategies = [
            {"signal": "BUY", "confidence": 0.9},
            {"signal": "SELL", "confidence": 0.8},
            {"signal": "HOLD", "confidence": 0.7},
        ]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "HOLD"

    def test_empty_strategies(self):
        direction, avg_conf, agree, total = compute_consensus([])
        assert direction == "HOLD"
        assert avg_conf == 0.0
        assert agree == 0
        assert total == 0

    def test_none_strategies(self):
        direction, avg_conf, agree, total = compute_consensus(None)
        assert direction == "HOLD"

    def test_single_strategy(self):
        strategies = [{"signal": "BUY", "confidence": 0.85}]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "BUY"
        assert agree == 1
        assert total == 1
        assert avg_conf == 0.85

    def test_all_hold(self):
        strategies = [
            {"signal": "HOLD", "confidence": 0.5},
            {"signal": "HOLD", "confidence": 0.6},
        ]
        direction, avg_conf, agree, total = compute_consensus(strategies)
        assert direction == "HOLD"
        assert agree == 2


class TestIsDuplicateSignal:
    """Tests for the is_duplicate_signal function."""

    def test_duplicate_within_15_min(self):
        now = datetime.now(timezone.utc)
        recent = [
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
            }
        ]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is True

    def test_not_duplicate_different_direction(self):
        now = datetime.now(timezone.utc)
        recent = [
            {
                "symbol": "BTC-USD",
                "action": "SELL",
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
            }
        ]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is False

    def test_not_duplicate_older_than_15_min(self):
        now = datetime.now(timezone.utc)
        recent = [
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "timestamp": (now - timedelta(minutes=20)).isoformat(),
            }
        ]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is False

    def test_not_duplicate_different_symbol(self):
        now = datetime.now(timezone.utc)
        recent = [
            {
                "symbol": "ETH-USD",
                "action": "BUY",
                "timestamp": (now - timedelta(minutes=5)).isoformat(),
            }
        ]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is False

    def test_empty_recent_signals(self):
        assert is_duplicate_signal([], "BTC-USD", "BUY") is False

    def test_none_recent_signals(self):
        assert is_duplicate_signal(None, "BTC-USD", "BUY") is False

    def test_boundary_exactly_15_min(self):
        now = datetime.now(timezone.utc)
        recent = [
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "timestamp": (now - timedelta(minutes=15)).isoformat(),
            }
        ]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is True

    def test_timestamp_with_z_suffix(self):
        now = datetime.now(timezone.utc)
        ts = (now - timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent = [{"symbol": "BTC-USD", "action": "BUY", "timestamp": ts}]
        assert is_duplicate_signal(recent, "BTC-USD", "BUY") is True


class TestCallMcpTool:
    """Tests for the _call_mcp_tool function."""

    def test_tool_to_mcp_server_mapping(self):
        assert TOOL_TO_MCP_SERVER["get_top_strategies"] == "strategy"
        assert TOOL_TO_MCP_SERVER["get_walk_forward"] == "strategy"
        assert TOOL_TO_MCP_SERVER["get_market_summary"] == "market"
        assert TOOL_TO_MCP_SERVER["get_candles"] == "market"
        assert TOOL_TO_MCP_SERVER["get_recent_signals"] == "signal"
        assert TOOL_TO_MCP_SERVER["emit_signal"] == "signal"

    @mock.patch("services.signal_generator_agent.agent.requests")
    def test_call_mcp_tool_success(self, mock_requests, mcp_urls):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": json.dumps([{"strategy_type": "momentum"}])}
            ]
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.post.return_value = mock_response

        result = _call_mcp_tool(
            "get_top_strategies", {"symbol": "BTC-USD", "limit": 10}, mcp_urls
        )

        assert result == [{"strategy_type": "momentum"}]
        mock_requests.post.assert_called_once_with(
            "http://strategy-mcp:8080/call-tool",
            json={
                "name": "get_top_strategies",
                "arguments": {"symbol": "BTC-USD", "limit": 10},
            },
            timeout=30,
        )

    @mock.patch("services.signal_generator_agent.agent.requests")
    def test_call_mcp_tool_emit_signal(self, mock_requests, mcp_urls):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": '{"signal_id": "sig-001"}'}
            ]
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.post.return_value = mock_response

        result = _call_mcp_tool(
            "emit_signal",
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
                "reasoning": "Strong consensus",
                "strategy_breakdown": [
                    {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.9}
                ],
            },
            mcp_urls,
        )

        assert result == {"signal_id": "sig-001"}
        mock_requests.post.assert_called_once_with(
            "http://signal-mcp:8080/call-tool",
            json={
                "name": "emit_signal",
                "arguments": {
                    "symbol": "BTC-USD",
                    "action": "BUY",
                    "confidence": 0.85,
                    "reasoning": "Strong consensus",
                    "strategy_breakdown": [
                        {
                            "strategy_type": "momentum",
                            "signal": "BUY",
                            "confidence": 0.9,
                        }
                    ],
                },
            },
            timeout=30,
        )


class TestGenerateSignal:
    """Tests for the generate_signal LLM agent loop."""

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    @mock.patch("services.signal_generator_agent.agent._call_mcp_tool")
    def test_generate_signal_returns_result(
        self, mock_mcp, mock_openai_cls, mcp_urls
    ):
        """Test that generate_signal returns a signal."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        result_json = {
            "symbol": "BTC-USD",
            "action": "BUY",
            "confidence": 0.82,
            "reasoning": "7/10 strategies agree on BUY with strong momentum",
            "strategy_breakdown": [
                {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.9},
                {"strategy_type": "trend_following", "signal": "BUY", "confidence": 0.85},
            ],
        }

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = json.dumps(result_json)

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=100)
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_signal("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        assert result["action"] == "BUY"
        assert result["confidence"] == 0.82
        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    @mock.patch("services.signal_generator_agent.agent._call_mcp_tool")
    def test_generate_signal_handles_tool_calls(
        self, mock_mcp, mock_openai_cls, mcp_urls
    ):
        """Test that tool calls are processed correctly."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # First response: tool call
        tool_call = mock.MagicMock()
        tool_call.id = "call-1"
        tool_call.function.name = "get_top_strategies"
        tool_call.function.arguments = json.dumps(
            {"symbol": "BTC-USD", "limit": 10}
        )

        tool_message = mock.MagicMock()
        tool_message.tool_calls = [tool_call]

        tool_response = mock.MagicMock()
        tool_response.choices = [mock.MagicMock(message=tool_message)]
        tool_response.usage = mock.MagicMock(total_tokens=50)

        # Second response: final result
        final_json = {
            "symbol": "BTC-USD",
            "action": "HOLD",
            "confidence": 0.45,
            "reasoning": "Mixed signals, defaulting to HOLD",
            "strategy_breakdown": [],
        }
        final_message = mock.MagicMock()
        final_message.tool_calls = None
        final_message.content = json.dumps(final_json)

        final_response = mock.MagicMock()
        final_response.choices = [mock.MagicMock(message=final_message)]
        final_response.usage = mock.MagicMock(total_tokens=80)

        mock_client.chat.completions.create.side_effect = [
            tool_response,
            final_response,
        ]
        mock_mcp.return_value = [
            {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.8}
        ]

        result = generate_signal("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        assert result["action"] == "HOLD"
        mock_mcp.assert_called_once_with(
            "get_top_strategies",
            {"symbol": "BTC-USD", "limit": 10},
            mcp_urls,
        )

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    @mock.patch("services.signal_generator_agent.agent._call_mcp_tool")
    def test_generate_signal_skipped_duplicate(
        self, mock_mcp, mock_openai_cls, mcp_urls
    ):
        """Test that skipped signals are returned correctly."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        result_json = {
            "skipped": True,
            "reason": "duplicate signal within 15 minutes",
        }

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = json.dumps(result_json)

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=100)
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_signal("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        assert result["skipped"] is True

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    @mock.patch("services.signal_generator_agent.agent._call_mcp_tool")
    def test_generate_signal_handles_mcp_error(
        self, mock_mcp, mock_openai_cls, mcp_urls
    ):
        """Test graceful handling of MCP errors."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        tool_call = mock.MagicMock()
        tool_call.id = "call-1"
        tool_call.function.name = "get_candles"
        tool_call.function.arguments = json.dumps(
            {"symbol": "BTC-USD", "limit": 50}
        )

        tool_message = mock.MagicMock()
        tool_message.tool_calls = [tool_call]

        tool_response = mock.MagicMock()
        tool_response.choices = [mock.MagicMock(message=tool_message)]
        tool_response.usage = mock.MagicMock(total_tokens=50)

        final_json = {
            "symbol": "BTC-USD",
            "action": "HOLD",
            "confidence": 0.3,
            "reasoning": "Insufficient data",
            "strategy_breakdown": [],
        }
        final_message = mock.MagicMock()
        final_message.tool_calls = None
        final_message.content = json.dumps(final_json)

        final_response = mock.MagicMock()
        final_response.choices = [mock.MagicMock(message=final_message)]
        final_response.usage = mock.MagicMock(total_tokens=80)

        mock_client.chat.completions.create.side_effect = [
            tool_response,
            final_response,
        ]
        mock_mcp.side_effect = Exception("Connection refused")

        result = generate_signal("BTC-USD", "test-key", mcp_urls)

        assert result is not None
        assert result["action"] == "HOLD"

    @mock.patch("services.signal_generator_agent.agent.OpenAI")
    def test_generate_signal_handles_unparseable_response(
        self, mock_openai_cls, mcp_urls
    ):
        """Test graceful handling of non-JSON LLM output."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "I cannot generate a signal."

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_signal("BTC-USD", "test-key", mcp_urls)

        assert result is None
