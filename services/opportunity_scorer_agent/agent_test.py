"""Tests for the Opportunity Scorer Agent."""

import json
from unittest import mock

import pytest

from services.opportunity_scorer_agent import agent


class TestComputeScore:
    """Tests for the scoring formula."""

    def test_perfect_score(self):
        """All components at max should yield 100."""
        score = agent.compute_score(
            confidence=1.0,
            sharpe_ratio=5.0,
            strategies_agreeing=5,
            total_strategies=5,
            atr_pct=0.0,
            signal_age_minutes=0,
        )
        assert score == 100.0

    def test_zero_score(self):
        """All components at min should yield near 0."""
        score = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=5,
            atr_pct=100.0,
            signal_age_minutes=60,
        )
        assert score == 0.0

    def test_confidence_weight(self):
        """Confidence contributes 25% of score."""
        score_high = agent.compute_score(
            confidence=1.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        score_low = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_high - score_low == pytest.approx(25.0)

    def test_expected_return_weight(self):
        """Expected return contributes 30% of score."""
        score_high = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=5.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        score_low = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_high - score_low == pytest.approx(30.0)

    def test_consensus_weight(self):
        """Consensus contributes 20% of score."""
        score_full = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=5,
            total_strategies=5,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        score_none = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=5,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_full - score_none == pytest.approx(20.0)

    def test_volatility_adj_weight(self):
        """Volatility adjustment contributes 15% of score."""
        score_low_vol = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=0.0,
            signal_age_minutes=60,
        )
        score_high_vol = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_low_vol - score_high_vol == pytest.approx(15.0)

    def test_freshness_weight(self):
        """Freshness contributes 10% of score."""
        score_fresh = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=0,
        )
        score_stale = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=0.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_fresh - score_stale == pytest.approx(10.0)

    def test_freshness_thresholds(self):
        """Test freshness score at boundary values."""
        # < 5 min = 100
        score_4min = agent.compute_score(
            confidence=0.0, sharpe_ratio=0.0, strategies_agreeing=0,
            total_strategies=1, atr_pct=10.0, signal_age_minutes=4,
        )
        # 5-15 min = 50
        score_10min = agent.compute_score(
            confidence=0.0, sharpe_ratio=0.0, strategies_agreeing=0,
            total_strategies=1, atr_pct=10.0, signal_age_minutes=10,
        )
        # > 15 min = 0
        score_20min = agent.compute_score(
            confidence=0.0, sharpe_ratio=0.0, strategies_agreeing=0,
            total_strategies=1, atr_pct=10.0, signal_age_minutes=20,
        )
        assert score_4min - score_10min == pytest.approx(5.0)
        assert score_10min - score_20min == pytest.approx(5.0)

    def test_expected_return_capped_at_100(self):
        """Sharpe ratio above 5 should cap expected_return_score at 100."""
        score_cap = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=10.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        score_at_5 = agent.compute_score(
            confidence=0.0,
            sharpe_ratio=5.0,
            strategies_agreeing=0,
            total_strategies=1,
            atr_pct=10.0,
            signal_age_minutes=60,
        )
        assert score_cap == score_at_5

    def test_volatility_clamped(self):
        """Volatility adj score should be clamped 0-100."""
        score_neg = agent.compute_score(
            confidence=0.0, sharpe_ratio=0.0, strategies_agreeing=0,
            total_strategies=1, atr_pct=50.0, signal_age_minutes=60,
        )
        assert score_neg >= 0

    def test_zero_total_strategies(self):
        """Zero total strategies should not cause division by zero."""
        score = agent.compute_score(
            confidence=0.5, sharpe_ratio=1.0, strategies_agreeing=0,
            total_strategies=0, atr_pct=5.0, signal_age_minutes=3,
        )
        assert score >= 0

    def test_realistic_scenario(self):
        """Test a realistic mid-range scenario."""
        score = agent.compute_score(
            confidence=0.75,
            sharpe_ratio=2.0,
            strategies_agreeing=3,
            total_strategies=5,
            atr_pct=3.0,
            signal_age_minutes=3,
        )
        # confidence_score = 75 * 0.25 = 18.75
        # expected_return = min(100, 40) * 0.30 = 12.0
        # consensus = (3/5)*100 * 0.20 = 12.0
        # volatility = max(0,min(100,100-30)) * 0.15 = 10.5
        # freshness = 100 * 0.10 = 10.0
        expected = 18.75 + 12.0 + 12.0 + 10.5 + 10.0
        assert score == pytest.approx(expected)


class TestAssignTier:
    """Tests for tier assignment."""

    def test_hot_tier(self):
        assert agent.assign_tier(100) == "HOT"
        assert agent.assign_tier(80) == "HOT"
        assert agent.assign_tier(90) == "HOT"

    def test_good_tier(self):
        assert agent.assign_tier(79) == "GOOD"
        assert agent.assign_tier(60) == "GOOD"
        assert agent.assign_tier(70) == "GOOD"

    def test_neutral_tier(self):
        assert agent.assign_tier(59) == "NEUTRAL"
        assert agent.assign_tier(40) == "NEUTRAL"
        assert agent.assign_tier(50) == "NEUTRAL"

    def test_low_tier(self):
        assert agent.assign_tier(39) == "LOW"
        assert agent.assign_tier(0) == "LOW"
        assert agent.assign_tier(20) == "LOW"

    def test_boundary_values(self):
        assert agent.assign_tier(80) == "HOT"
        assert agent.assign_tier(79.9) == "GOOD"
        assert agent.assign_tier(60) == "GOOD"
        assert agent.assign_tier(59.9) == "NEUTRAL"
        assert agent.assign_tier(40) == "NEUTRAL"
        assert agent.assign_tier(39.9) == "LOW"


class TestCallMcpTool:
    """Tests for MCP tool dispatching."""

    def test_unknown_tool_returns_error(self):
        result = agent._call_mcp_tool("unknown_tool", {}, {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_missing_server_url_returns_error(self):
        result = agent._call_mcp_tool("get_volatility", {"symbol": "BTC-USD"}, {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "No URL configured" in parsed["error"]

    @mock.patch("requests.post")
    def test_successful_mcp_call(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": json.dumps({"atr": 0.5})}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        mcp_urls = {"market": "http://market:8080"}
        result = agent._call_mcp_tool(
            "get_volatility", {"symbol": "BTC-USD"}, mcp_urls
        )

        mock_post.assert_called_once_with(
            "http://market:8080/call-tool",
            json={
                "name": "get_volatility",
                "arguments": {"symbol": "BTC-USD"},
            },
            timeout=30,
        )
        parsed = json.loads(result)
        assert parsed["atr"] == 0.5

    @mock.patch("requests.post")
    def test_mcp_call_http_error(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.RequestException("Connection refused")

        mcp_urls = {"market": "http://market:8080"}
        result = agent._call_mcp_tool(
            "get_volatility", {"symbol": "BTC-USD"}, mcp_urls
        )

        parsed = json.loads(result)
        assert "error" in parsed


class TestToolToServerMapping:
    """Tests for tool-to-server routing."""

    def test_strategy_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["get_performance"] == "strategy"

    def test_market_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["get_volatility"] == "market"

    def test_signal_tools_route_correctly(self):
        assert agent.TOOL_TO_SERVER["log_decision"] == "signal"
        assert agent.TOOL_TO_SERVER["get_recent_signals"] == "signal"


class TestRunScorer:
    """Tests for the main agent loop."""

    @mock.patch("requests.post")
    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    def test_scorer_completes_with_decision(self, mock_openai_cls, mock_requests_post):
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        # First LLM call returns tool call
        tool_call_1 = mock.Mock()
        tool_call_1.id = "tc_1"
        tool_call_1.function.name = "get_recent_signals"
        tool_call_1.function.arguments = json.dumps({"limit": 1})

        msg_1 = mock.Mock()
        msg_1.tool_calls = [tool_call_1]
        msg_1.content = None
        msg_1.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {
                        "name": "get_recent_signals",
                        "arguments": '{"limit":1}',
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
        msg_2.content = json.dumps({
            "signal_id": "sig_1",
            "score": 72.5,
            "tier": "GOOD",
            "reasoning": "Strong consensus with moderate volatility",
        })
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
        mock_http_resp.json.return_value = {
            "content": [{"type": "text", "text": json.dumps([{
                "id": "sig_1",
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.8,
                "strategy_breakdown": [
                    {"strategy_type": "momentum", "signal": "BUY", "confidence": 0.8}
                ],
            }])}]
        }
        mock_http_resp.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_http_resp

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "market": "http://market:8080",
            "signal": "http://signal:8080",
        }

        result = agent.run_scorer("test-key", mcp_urls)

        assert result is not None
        parsed = json.loads(result)
        assert parsed["tier"] == "GOOD"
        assert parsed["score"] == 72.5

        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @mock.patch("services.opportunity_scorer_agent.agent.OpenAI")
    def test_scorer_handles_max_iterations(self, mock_openai_cls):
        mock_client = mock.Mock()
        mock_openai_cls.return_value = mock_client

        tool_call = mock.Mock()
        tool_call.id = "tc_loop"
        tool_call.function.name = "get_recent_signals"
        tool_call.function.arguments = json.dumps({"limit": 1})

        msg = mock.Mock()
        msg.tool_calls = [tool_call]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_loop",
                    "function": {
                        "name": "get_recent_signals",
                        "arguments": '{"limit":1}',
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

        mcp_urls = {"signal": "http://signal:8080"}

        with mock.patch("requests.post") as mock_post:
            mock_http = mock.Mock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "content": [{"type": "text", "text": json.dumps([])}]
            }
            mock_http.raise_for_status.return_value = None
            mock_post.return_value = mock_http

            result = agent.run_scorer("test-key", mcp_urls)

        assert result is None


class TestMcpToolDefinitions:
    """Tests for tool definitions matching expected MCP signatures."""

    def test_all_required_tools_present(self):
        tool_names = {t["function"]["name"] for t in agent.MCP_TOOLS}
        assert "get_recent_signals" in tool_names
        assert "get_volatility" in tool_names
        assert "get_performance" in tool_names
        assert "log_decision" in tool_names

    def test_log_decision_has_required_params(self):
        log_tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "log_decision"
        )
        required = log_tool["function"]["parameters"]["required"]
        assert "signal_id" in required
        assert "score" in required
        assert "tier" in required
        assert "reasoning" in required
        assert "tool_calls" in required
        assert "model_used" in required
        assert "latency_ms" in required
        assert "tokens" in required

    def test_get_volatility_has_symbol_required(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "get_volatility"
        )
        assert "symbol" in tool["function"]["parameters"]["required"]

    def test_get_performance_has_impl_id_required(self):
        tool = next(
            t for t in agent.MCP_TOOLS if t["function"]["name"] == "get_performance"
        )
        assert "impl_id" in tool["function"]["parameters"]["required"]


class TestSystemPrompt:
    """Tests for system prompt skill content."""

    def test_score_signal_skill_present(self):
        assert "/score-signal" in agent.SYSTEM_PROMPT

    def test_assign_tier_skill_present(self):
        assert "/assign-tier" in agent.SYSTEM_PROMPT

    def test_scoring_formula_weights(self):
        assert "0.25" in agent.SYSTEM_PROMPT
        assert "0.30" in agent.SYSTEM_PROMPT
        assert "0.20" in agent.SYSTEM_PROMPT
        assert "0.15" in agent.SYSTEM_PROMPT
        assert "0.10" in agent.SYSTEM_PROMPT

    def test_tier_boundaries(self):
        assert "80-100" in agent.SYSTEM_PROMPT
        assert "60-79" in agent.SYSTEM_PROMPT
        assert "40-59" in agent.SYSTEM_PROMPT
        assert "0-39" in agent.SYSTEM_PROMPT

    def test_freshness_thresholds_in_prompt(self):
        assert "5 min" in agent.SYSTEM_PROMPT
        assert "15 min" in agent.SYSTEM_PROMPT
