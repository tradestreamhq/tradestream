"""Tests for agent decision models."""

import json

from services.autonomous_runner.decision_models import (
    MAX_TOOL_CALLS,
    MAX_TOOL_CALL_RESULT_SIZE,
    AgentDecision,
    _truncate_if_needed,
    _validate_tool_calls,
)
from services.autonomous_runner.signal_fusion import SignalAction, SourceSignal


class TestAgentDecision:
    def test_default_fields(self):
        d = AgentDecision()
        assert d.decision_id
        assert d.symbol == ""
        assert d.action == ""
        assert d.confidence == 0.0
        assert d.agent_type == "autonomous_runner"

    def test_compute_opportunity_score(self):
        d = AgentDecision(
            symbol="BTC-USD",
            action="BUY",
            confidence=0.85,
            fusion_agreement_ratio=0.80,
        )
        score = d.compute_opportunity_score()
        assert score > 0
        assert d.opportunity_tier in ("HOT", "GOOD", "NEUTRAL", "LOW")
        assert d.opportunity_factors.get("total_score") == score

    def test_opportunity_tier_hot(self):
        d = AgentDecision(confidence=0.95, fusion_agreement_ratio=1.0)
        d.compute_opportunity_score()
        assert d.opportunity_tier in ("HOT", "GOOD")

    def test_opportunity_tier_low(self):
        d = AgentDecision(confidence=0.3, fusion_agreement_ratio=0.2)
        d.compute_opportunity_score()
        assert d.opportunity_tier in ("LOW", "NEUTRAL")

    def test_to_dict(self):
        d = AgentDecision(
            symbol="ETH-USD",
            action="SELL",
            confidence=0.75,
            reasoning="Test reasoning",
        )
        result = d.to_dict()
        assert result["symbol"] == "ETH-USD"
        assert result["action"] == "SELL"
        assert result["confidence"] == 0.75
        assert result["reasoning"] == "Test reasoning"
        assert "decision_id" in result
        assert "created_at" in result

    def test_to_dict_with_source_signals(self):
        d = AgentDecision(
            symbol="BTC-USD",
            action="BUY",
            source_signals=[
                SourceSignal(source="strategy", action=SignalAction.BUY, confidence=0.9),
            ],
        )
        result = d.to_dict()
        assert len(result["source_signals"]) == 1
        assert result["source_signals"][0]["source"] == "strategy"

    def test_validate_jsonb_sizes(self):
        d = AgentDecision(
            tool_calls={"calls": [{"tool": "test", "result": {"data": "x" * 10000}}]},
        )
        d.validate_jsonb_sizes()
        call = d.tool_calls["calls"][0]
        # Result should be truncated since it exceeds 5KB
        if len(json.dumps({"data": "x" * 10000})) > MAX_TOOL_CALL_RESULT_SIZE:
            assert call["result"].get("truncated") is True


class TestValidateToolCalls:
    def test_within_limits(self):
        data = {"calls": [{"tool": "test", "result": {"ok": True}}]}
        result = _validate_tool_calls(data)
        assert len(result["calls"]) == 1

    def test_truncates_excess_calls(self):
        calls = [{"tool": f"test_{i}", "result": {}} for i in range(100)]
        data = {"calls": calls}
        result = _validate_tool_calls(data)
        assert len(result["calls"]) == MAX_TOOL_CALLS
        assert result.get("truncated") is True

    def test_truncates_large_results(self):
        large_result = {"data": "x" * 10000}
        data = {"calls": [{"tool": "test", "result": large_result}]}
        result = _validate_tool_calls(data)
        call = result["calls"][0]
        if len(json.dumps(large_result)) > MAX_TOOL_CALL_RESULT_SIZE:
            assert call["result"]["truncated"] is True


class TestTruncateIfNeeded:
    def test_small_data_unchanged(self):
        data = {"key": "value"}
        result = _truncate_if_needed(data, 1000)
        assert result == data

    def test_large_data_truncated(self):
        data = {"key": "x" * 100000}
        result = _truncate_if_needed(data, 1000)
        assert result.get("truncated") is True
        assert "original_size" in result
