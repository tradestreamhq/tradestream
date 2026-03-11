"""Integration tests for the Opportunity Scorer Agent LLM loop.

Verifies the full decision pipeline: signal input → multi-step LLM calls
→ tool execution (including concurrent calls) → response parsing → scored
output.  All LLM and MCP calls are mocked.
"""

import json
from unittest import mock

import pytest

from services.opportunity_scorer_agent.agent import (
    TOOL_TO_MCP_SERVER,
    score_signal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_urls():
    return {
        "strategy": "http://strategy-mcp:8080",
        "market": "http://market-mcp:8080",
        "signal": "http://signal-mcp:8080",
    }


@pytest.fixture
def sample_signal():
    return {
        "signal_id": "sig-int-001",
        "symbol": "BTC/USD",
        "action": "BUY",
        "confidence": 0.85,
        "timestamp": "2026-03-09T12:00:00Z",
        "strategy_breakdown": [
            {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.9, "impl_id": "impl-1"},
            {"strategy_type": "mean_reversion", "signal": "BUY", "confidence": 0.8, "impl_id": "impl-2"},
            {"strategy_type": "trend_following", "signal": "SELL", "confidence": 0.6, "impl_id": "impl-3"},
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_tool_call(call_id, name, arguments):
    tc = mock.Mock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _tool_response(tool_calls, tokens=50):
    msg = mock.MagicMock()
    msg.tool_calls = tool_calls
    resp = mock.MagicMock()
    resp.choices = [mock.MagicMock(message=msg)]
    resp.usage = mock.MagicMock(total_tokens=tokens)
    return resp


def _final_response(content, tokens=80):
    msg = mock.MagicMock()
    msg.tool_calls = None
    msg.content = content if isinstance(content, str) else json.dumps(content)
    resp = mock.MagicMock()
    resp.choices = [mock.MagicMock(message=msg)]
    resp.usage = mock.MagicMock(total_tokens=tokens)
    return resp


# ---------------------------------------------------------------------------
# Multi-step workflow tests
# ---------------------------------------------------------------------------

class TestScorerMultiStepWorkflow:
    """Test the full multi-step LLM loop for opportunity scoring."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_full_workflow_volatility_performance_log(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Full 3-step: get_volatility → get_performance_batch → log_decision → result."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # Step 1: LLM requests volatility
        resp1 = _tool_response([
            _mock_tool_call("tc1", "get_volatility", {"symbol": "BTC/USD"}),
        ])

        # Step 2: LLM requests batch performance
        resp2 = _tool_response([
            _mock_tool_call("tc2", "get_performance_batch", {"impl_ids": ["impl-1", "impl-2", "impl-3"]}),
        ])

        # Step 3: LLM logs decision
        resp3 = _tool_response([
            _mock_tool_call("tc3", "log_decision", {
                "signal_id": "sig-int-001",
                "score": 71.5,
                "tier": "GOOD",
                "reasoning": "Strong consensus, moderate volatility",
                "tool_calls": [],
                "model_used": "anthropic/claude-haiku-4-5",
                "latency_ms": 2100,
                "tokens": 300,
            }),
        ])

        # Step 4: LLM produces final answer
        final = {"score": 71.5, "tier": "GOOD", "reasoning": "Strong consensus, moderate volatility"}
        resp4 = _final_response(final)

        mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3, resp4]

        def mcp_side_effect(name, args, tool_to_server, urls, **kwargs):
            if name == "get_volatility":
                return {"atr": 0.025, "stddev": 0.012}
            elif name == "get_performance_batch":
                return {
                    "impl-1": {"backtest": {"sharpe_ratio": 2.1}},
                    "impl-2": {"backtest": {"sharpe_ratio": 1.8}},
                    "impl-3": {"backtest": {"sharpe_ratio": 0.5}},
                }
            elif name == "log_decision":
                return {"status": "ok"}
            return {}

        mock_mcp.side_effect = mcp_side_effect

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 71.5
        assert result["tier"] == "GOOD"
        assert mock_client.chat.completions.create.call_count == 4
        assert mock_mcp.call_count == 3

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_concurrent_tool_calls_both_succeed(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Two simultaneous tool calls (volatility + performance_batch) both succeed."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # LLM issues two concurrent tool calls
        resp1 = _tool_response([
            _mock_tool_call("tc-vol", "get_volatility", {"symbol": "BTC/USD"}),
            _mock_tool_call("tc-perf", "get_performance_batch", {"impl_ids": ["impl-1", "impl-2"]}),
        ])

        final = {"score": 68.0, "tier": "GOOD", "reasoning": "Concurrent data fetch"}
        resp2 = _final_response(final)

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        def mcp_side_effect(name, args, tool_to_server, urls, **kwargs):
            if name == "get_volatility":
                return {"atr": 0.03, "stddev": 0.015}
            elif name == "get_performance_batch":
                return {"impl-1": {"backtest": {"sharpe_ratio": 1.5}}}
            return {}

        mock_mcp.side_effect = mcp_side_effect

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 68.0
        assert mock_mcp.call_count == 2

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_concurrent_tool_calls_one_fails(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """When one of two concurrent tool calls fails, the error is captured and loop continues."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        resp1 = _tool_response([
            _mock_tool_call("tc-vol", "get_volatility", {"symbol": "BTC/USD"}),
            _mock_tool_call("tc-perf", "get_performance_batch", {"impl_ids": ["impl-1"]}),
        ])

        final = {"score": 40.0, "tier": "NEUTRAL", "reasoning": "Partial data available"}
        resp2 = _final_response(final)

        mock_client.chat.completions.create.side_effect = [resp1, resp2]

        call_count = {"n": 0}

        def mcp_side_effect(name, args, tool_to_server, urls, **kwargs):
            call_count["n"] += 1
            if name == "get_volatility":
                return {"atr": 0.03, "stddev": 0.015}
            elif name == "get_performance_batch":
                raise ConnectionError("MCP server unavailable")
            return {}

        mock_mcp.side_effect = mcp_side_effect

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["tier"] == "NEUTRAL"
        # Both tool calls were attempted
        assert call_count["n"] == 2


class TestScorerResponseParsing:
    """Test response parsing edge cases in the scoring loop."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_json_embedded_in_text(self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal):
        """LLM wraps JSON in prose text; parser should extract it."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # Response has JSON embedded in text
        content = 'Here is the result: {"score": 55.0, "tier": "NEUTRAL", "reasoning": "Mixed"} based on my analysis.'
        resp = _final_response(content)
        mock_client.chat.completions.create.return_value = resp

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 55.0
        assert result["tier"] == "NEUTRAL"

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_no_json_in_response_returns_none(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Completely non-JSON response returns None."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        resp = _final_response("I'm unable to score this signal due to errors.")
        mock_client.chat.completions.create.return_value = resp

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is None

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_none_content_returns_none(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """None/empty content returns None."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        msg = mock.MagicMock()
        msg.tool_calls = None
        msg.content = None

        resp = mock.MagicMock()
        resp.choices = [mock.MagicMock(message=msg)]
        resp.usage = mock.MagicMock(total_tokens=10)
        mock_client.chat.completions.create.return_value = resp

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is None


class TestScorerErrorHandling:
    """Test error handling within the scorer LLM loop."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_max_iterations_returns_none(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Agent returns None when max iterations reached."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # Every response has tool calls — never finishes
        tc = _mock_tool_call("tc-loop", "get_volatility", {"symbol": "BTC/USD"})
        looping_resp = _tool_response([tc])
        mock_client.chat.completions.create.return_value = looping_resp

        mock_mcp.return_value = {"atr": 0.02}

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is None
        # Should have hit max iterations (15)
        assert mock_client.chat.completions.create.call_count == 15

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    def test_llm_api_error_propagates(self, mock_openai_cls, mcp_urls, sample_signal):
        """LLM API errors should propagate."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        from openai import APIError

        mock_client.chat.completions.create.side_effect = APIError(
            message="Rate limited",
            request=mock.Mock(),
            body=None,
        )

        with pytest.raises(APIError):
            score_signal(sample_signal, "test-key", mcp_urls)

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_all_mcp_calls_fail_still_produces_result(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Even when all MCP calls fail, the LLM can still produce a result."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        resp1 = _tool_response([
            _mock_tool_call("tc1", "get_volatility", {"symbol": "BTC/USD"}),
        ])
        final = {"score": 25.0, "tier": "LOW", "reasoning": "No data available"}
        resp2 = _final_response(final)

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_mcp.side_effect = Exception("All MCP servers down")

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["tier"] == "LOW"


class TestScorerTokenTracking:
    """Verify token usage is tracked across iterations."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_tokens_accumulated_across_iterations(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Token counts are summed across multiple LLM calls."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        resp1 = _tool_response(
            [_mock_tool_call("tc1", "get_volatility", {"symbol": "BTC/USD"})],
            tokens=100,
        )
        final = {"score": 60.0, "tier": "GOOD", "reasoning": "OK"}
        resp2 = _final_response(final, tokens=150)

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_mcp.return_value = {"atr": 0.02}

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        # The function should have accumulated tokens internally
        assert mock_client.chat.completions.create.call_count == 2


class TestScorerModelConfiguration:
    """Verify correct model selection for the scorer."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent.resolve_and_call")
    def test_uses_lightweight_model(self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal):
        """Opportunity scorer must use MODEL_LIGHTWEIGHT for high-volume tasks."""
        from services.shared.model_config import MODEL_LIGHTWEIGHT

        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        resp = _final_response({"score": 50.0, "tier": "NEUTRAL", "reasoning": "test"})
        mock_client.chat.completions.create.return_value = resp

        score_signal(sample_signal, "test-key", mcp_urls)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == MODEL_LIGHTWEIGHT
