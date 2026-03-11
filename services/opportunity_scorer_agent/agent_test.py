"""Tests for the Opportunity Scorer Agent."""

import json
from unittest import mock

import pytest

from services.opportunity_scorer_agent.agent import (
    TOOL_TO_MCP_SERVER,
    _call_mcp_tool,
    assign_tier,
    compute_score,
    score_signal,
)


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
        "signal_id": "sig-001",
        "symbol": "BTC/USD",
        "action": "BUY",
        "confidence": 0.85,
        "timestamp": "2026-03-09T12:00:00Z",
        "strategy_breakdown": [
            {
                "strategy_type": "momentum",
                "signal": "BUY",
                "confidence": 0.9,
                "impl_id": "impl-1",
            },
            {
                "strategy_type": "mean_reversion",
                "signal": "BUY",
                "confidence": 0.8,
                "impl_id": "impl-2",
            },
            {
                "strategy_type": "trend_following",
                "signal": "SELL",
                "confidence": 0.6,
                "impl_id": "impl-3",
            },
        ],
    }


class TestComputeScore:
    """Tests for the compute_score function."""

    def test_perfect_score(self):
        """All components at maximum should yield a high score."""
        score = compute_score(
            confidence=1.0,
            sharpe_ratio=5.0,
            strategies_agreeing=5,
            total_strategies=5,
            atr_pct=0.0,
            signal_age_minutes=1,
        )
        # confidence: 100*0.25=25, expected_return: 100*0.30=30,
        # consensus: 100*0.20=20, vol_adj: 100*0.15=15, fresh: 100*0.10=10
        assert score == 100.0

    def test_minimum_score(self):
        """All components at minimum should yield 0."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=5,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score == 0.0

    def test_confidence_weight(self):
        """Test confidence contributes 25% of score."""
        score = compute_score(
            confidence=1.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score == 25.0

    def test_expected_return_weight(self):
        """Test expected return contributes 30% of score."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=5.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score == 30.0

    def test_expected_return_capped_at_100(self):
        """Sharpe > 5 should cap expected_return_score at 100."""
        score_at_5 = compute_score(
            confidence=0.0,
            sharpe_ratio=5.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        score_at_10 = compute_score(
            confidence=0.0,
            sharpe_ratio=10.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score_at_5 == score_at_10

    def test_consensus_weight(self):
        """Test consensus contributes 20% of score."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=3,
            total_strategies=3,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score == 20.0

    def test_volatility_adj_moderate(self):
        """Moderate volatility (ATR 2%) gives reasonable score."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=2.0,
            signal_age_minutes=20,
        )
        # vol_adj = 100 - 20 = 80, * 0.15 = 12
        assert score == 12.0

    def test_volatility_adj_extreme(self):
        """Extreme volatility (ATR 10%+) clamps to 0."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=20,
        )
        assert score == 0.0

    def test_freshness_under_5_min(self):
        """Signal < 5 min old gets 100 freshness."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=3,
        )
        # freshness: 100 * 0.10 = 10
        assert score == 10.0

    def test_freshness_5_to_15_min(self):
        """Signal 5-15 min old gets 50 freshness."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=10,
        )
        # freshness: 50 * 0.10 = 5
        assert score == 5.0

    def test_freshness_over_15_min(self):
        """Signal > 15 min old gets 0 freshness."""
        score = compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=100.0,
            signal_age_minutes=20,
        )
        assert score == 0.0

    def test_zero_total_strategies(self):
        """Zero total strategies should not cause division by zero."""
        score = compute_score(
            confidence=0.5,
            sharpe_ratio=2.0,
            strategies_agreeing=0,
            total_strategies=0,
            atr_pct=3.0,
            signal_age_minutes=2,
        )
        # confidence: 50*0.25=12.5, expected: 40*0.30=12, consensus: 0,
        # vol_adj: 70*0.15=10.5, fresh: 100*0.10=10
        assert score == 45.0

    def test_realistic_scenario(self):
        """Test a realistic scoring scenario."""
        score = compute_score(
            confidence=0.85,
            sharpe_ratio=2.1,
            strategies_agreeing=2,
            total_strategies=3,
            atr_pct=2.5,
            signal_age_minutes=2,
        )
        # confidence: 85*0.25=21.25
        # expected_return: min(100,42)*0.30=12.6
        # consensus: (2/3*100)*0.20=13.33
        # vol_adj: (100-25)*0.15=11.25
        # freshness: 100*0.10=10
        expected = 21.25 + 12.6 + 13.33 + 11.25 + 10.0
        assert abs(score - round(expected, 2)) < 0.01


class TestAssignTier:
    """Tests for the assign_tier function."""

    def test_hot_tier(self):
        assert assign_tier(80) == "HOT"
        assert assign_tier(90) == "HOT"
        assert assign_tier(100) == "HOT"

    def test_good_tier(self):
        assert assign_tier(60) == "GOOD"
        assert assign_tier(70) == "GOOD"
        assert assign_tier(79) == "GOOD"

    def test_neutral_tier(self):
        assert assign_tier(40) == "NEUTRAL"
        assert assign_tier(50) == "NEUTRAL"
        assert assign_tier(59) == "NEUTRAL"

    def test_low_tier(self):
        assert assign_tier(0) == "LOW"
        assert assign_tier(20) == "LOW"
        assert assign_tier(39) == "LOW"

    def test_boundary_values(self):
        assert assign_tier(79.99) == "GOOD"
        assert assign_tier(80.0) == "HOT"
        assert assign_tier(59.99) == "NEUTRAL"
        assert assign_tier(60.0) == "GOOD"
        assert assign_tier(39.99) == "LOW"
        assert assign_tier(40.0) == "NEUTRAL"


class TestCallMcpTool:
    """Tests for the _call_mcp_tool function."""

    def test_tool_to_mcp_server_mapping(self):
        assert TOOL_TO_MCP_SERVER["get_recent_signals"] == "signal"
        assert TOOL_TO_MCP_SERVER["get_volatility"] == "market"
        assert TOOL_TO_MCP_SERVER["get_performance"] == "strategy"
        assert TOOL_TO_MCP_SERVER["get_performance_batch"] == "strategy"
        assert TOOL_TO_MCP_SERVER["log_decision"] == "signal"

    @mock.patch("services.opportunity_scorer_agent.agent.requests")
    def test_call_mcp_tool_success(self, mock_requests, mcp_urls):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"atr": 0.025, "stddev": 0.012}'}]
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.post.return_value = mock_response

        result = _call_mcp_tool("get_volatility", {"symbol": "BTC/USD"}, mcp_urls)

        assert result == {"atr": 0.025, "stddev": 0.012}
        mock_requests.post.assert_called_once_with(
            "http://market-mcp:8080/call-tool",
            json={
                "name": "get_volatility",
                "arguments": {"symbol": "BTC/USD"},
            },
            timeout=30,
        )

    @mock.patch("services.opportunity_scorer_agent.agent.requests")
    def test_call_mcp_tool_log_decision(self, mock_requests, mcp_urls):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"status": "ok"}'}]
        }
        mock_response.raise_for_status = mock.MagicMock()
        mock_requests.post.return_value = mock_response

        result = _call_mcp_tool(
            "log_decision",
            {
                "signal_id": "sig-001",
                "score": 75.0,
                "tier": "GOOD",
                "reasoning": "test",
                "tool_calls": [],
                "model_used": "anthropic/claude-3-5-haiku",
                "latency_ms": 1200,
                "tokens": 500,
            },
            mcp_urls,
        )

        assert result == {"status": "ok"}
        mock_requests.post.assert_called_once_with(
            "http://signal-mcp:8080/call-tool",
            json={
                "name": "log_decision",
                "arguments": {
                    "signal_id": "sig-001",
                    "score": 75.0,
                    "tier": "GOOD",
                    "reasoning": "test",
                    "tool_calls": [],
                    "model_used": "anthropic/claude-3-5-haiku",
                    "latency_ms": 1200,
                    "tokens": 500,
                },
            },
            timeout=30,
        )


class TestScoreSignal:
    """Tests for the score_signal LLM agent loop."""

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent._call_mcp_tool")
    def test_score_signal_returns_result(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test that score_signal returns a score and tier."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        result_json = {
            "score": 72.5,
            "tier": "GOOD",
            "reasoning": "Strong consensus with moderate volatility",
        }

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = json.dumps(result_json)

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=100)
        mock_client.chat.completions.create.return_value = mock_response

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 72.5
        assert result["tier"] == "GOOD"
        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent._call_mcp_tool")
    def test_score_signal_handles_tool_calls(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test that tool calls are processed correctly."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # First response: tool call
        tool_call = mock.MagicMock()
        tool_call.id = "call-1"
        tool_call.function.name = "get_volatility"
        tool_call.function.arguments = json.dumps({"symbol": "BTC/USD"})

        tool_message = mock.MagicMock()
        tool_message.tool_calls = [tool_call]

        tool_response = mock.MagicMock()
        tool_response.choices = [mock.MagicMock(message=tool_message)]
        tool_response.usage = mock.MagicMock(total_tokens=50)

        # Second response: final result
        final_json = {
            "score": 65.0,
            "tier": "GOOD",
            "reasoning": "Moderate opportunity",
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
        mock_mcp.return_value = {"atr": 0.025, "stddev": 0.012}

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 65.0
        mock_mcp.assert_called_once_with(
            "get_volatility", {"symbol": "BTC/USD"}, mcp_urls
        )

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent._call_mcp_tool")
    def test_score_signal_concurrent_tool_calls(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test that multiple tool calls in one response are executed concurrently."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        # First response: two tool calls at once (volatility + batch performance)
        tc_vol = mock.MagicMock()
        tc_vol.id = "call-vol"
        tc_vol.function.name = "get_volatility"
        tc_vol.function.arguments = json.dumps({"symbol": "BTC/USD"})

        tc_batch = mock.MagicMock()
        tc_batch.id = "call-batch"
        tc_batch.function.name = "get_performance_batch"
        tc_batch.function.arguments = json.dumps(
            {"impl_ids": ["impl-1", "impl-2", "impl-3"]}
        )

        tool_message = mock.MagicMock()
        tool_message.tool_calls = [tc_vol, tc_batch]

        tool_response = mock.MagicMock()
        tool_response.choices = [mock.MagicMock(message=tool_message)]
        tool_response.usage = mock.MagicMock(total_tokens=50)

        # Final response
        final_json = {
            "score": 72.5,
            "tier": "GOOD",
            "reasoning": "Batched performance data",
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

        def mcp_side_effect(name, args, urls):
            if name == "get_volatility":
                return {"atr": 0.025, "stddev": 0.012}
            elif name == "get_performance_batch":
                return {
                    "impl-1": {"backtest": {"sharpe_ratio": 1.5}},
                    "impl-2": {"backtest": {"sharpe_ratio": 2.0}},
                    "impl-3": {"backtest": {"sharpe_ratio": 0.8}},
                }
            return {}

        mock_mcp.side_effect = mcp_side_effect

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["score"] == 72.5
        # Both tools should have been called
        assert mock_mcp.call_count == 2

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    @mock.patch("services.opportunity_scorer_agent.agent._call_mcp_tool")
    def test_score_signal_handles_mcp_error(
        self, mock_mcp, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test graceful handling of MCP errors."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        tool_call = mock.MagicMock()
        tool_call.id = "call-1"
        tool_call.function.name = "get_volatility"
        tool_call.function.arguments = json.dumps({"symbol": "BTC/USD"})

        tool_message = mock.MagicMock()
        tool_message.tool_calls = [tool_call]

        tool_response = mock.MagicMock()
        tool_response.choices = [mock.MagicMock(message=tool_message)]
        tool_response.usage = mock.MagicMock(total_tokens=50)

        final_json = {
            "score": 30.0,
            "tier": "LOW",
            "reasoning": "Insufficient data",
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

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is not None
        assert result["tier"] == "LOW"

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    def test_score_signal_handles_unparseable_response(
        self, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test graceful handling of non-JSON LLM output."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "I cannot score this signal."

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is None

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    def test_score_signal_handles_empty_response(
        self, mock_openai_cls, mcp_urls, sample_signal
    ):
        """Test that empty content returns None."""
        mock_client = mock.MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None
        mock_message.content = ""

        mock_response = mock.MagicMock()
        mock_response.choices = [mock.MagicMock(message=mock_message)]
        mock_response.usage = mock.MagicMock(total_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        result = score_signal(sample_signal, "test-key", mcp_urls)

        assert result is None
