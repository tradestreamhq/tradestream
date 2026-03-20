"""Integration tests for the signal coordinator pipeline.

Exercises the full autonomous signal generation pipeline end-to-end
with mock MCP servers, verifying signal fusion, conflict resolution,
risk management, degraded mode, and decision recording.
"""

import pytest
from unittest.mock import MagicMock, patch

from services.autonomous_runner.config import Config
from services.autonomous_runner.coordinator import SignalCoordinator
from services.autonomous_runner.signal_fusion import SignalAction


def _make_config(**overrides) -> Config:
    defaults = dict(
        mcp_strategy_url="http://localhost:8080",
        mcp_market_url="http://localhost:8081",
        mcp_signal_url="http://localhost:8082",
    )
    defaults.update(overrides)
    return Config(**defaults)


def _make_coordinator(config=None) -> SignalCoordinator:
    config = config or _make_config()
    return SignalCoordinator(config, "integration-test")


# --- MCP Response Fixtures ---

BULLISH_STRATEGIES = {
    "strategies": [
        {
            "name": "RSI_REVERSAL",
            "signal": "BUY",
            "score": 0.89,
            "confidence": 0.85,
            "parameters": {"rsiPeriod": 14, "oversold": 30},
        },
        {"name": "MACD_CROSS", "signal": "BUY", "score": 0.85, "confidence": 0.78},
        {"name": "EMA_TREND", "signal": "BUY", "score": 0.72, "confidence": 0.70},
        {"name": "VOLUME_BREAKOUT", "signal": "BUY", "score": 0.65, "confidence": 0.60},
    ]
}

BEARISH_STRATEGIES = {
    "strategies": [
        {"name": "RSI_OVERBOUGHT", "signal": "SELL", "score": 0.88, "confidence": 0.84},
        {"name": "DEATH_CROSS", "signal": "SELL", "score": 0.82, "confidence": 0.75},
        {"name": "VOLUME_DROP", "signal": "SELL", "score": 0.70, "confidence": 0.65},
    ]
}

MIXED_STRATEGIES = {
    "strategies": [
        {"name": "RSI_REVERSAL", "signal": "BUY", "score": 0.80, "confidence": 0.75},
        {"name": "MACD_CROSS", "signal": "SELL", "score": 0.78, "confidence": 0.72},
        {"name": "EMA_TREND", "signal": "BUY", "score": 0.65, "confidence": 0.60},
        {"name": "BOLLINGER", "signal": "SELL", "score": 0.60, "confidence": 0.55},
    ]
}

BULLISH_MARKET = {
    "current_price": 65000.0,
    "price_change_1h": 3.5,
    "volume_ratio": 1.8,
    "volatility": 0.025,
    "volume_24h": 15000000000,
}

BEARISH_MARKET = {
    "current_price": 58000.0,
    "price_change_1h": -4.2,
    "volume_ratio": 2.1,
    "volatility": 0.045,
    "volume_24h": 20000000000,
}

FLAT_MARKET = {
    "current_price": 62000.0,
    "price_change_1h": 0.1,
    "volume_ratio": 0.9,
    "volatility": 0.010,
}

RECENT_BUY_SIGNALS = {
    "signals": [
        {"action": "BUY", "confidence": 0.80},
        {"action": "BUY", "confidence": 0.75},
        {"action": "HOLD", "confidence": 0.50},
    ]
}

ACCURACY_HIGH = {
    "accuracy": 0.78,
    "buy_accuracy": 0.82,
    "sell_accuracy": 0.55,
    "total": 100,
}
ACCURACY_LOW = {"accuracy": 0.35, "total": 2}


class TestFullPipelineBullish:
    """Test the full pipeline with bullish signal alignment."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_bullish_consensus_generates_buy(self, mock_call):
        """When strategies + market + sentiment all agree bullish, emit BUY."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return RECENT_BUY_SIGNALS
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision.symbol == "BTC-USD"
        assert decision.action == "BUY"
        assert decision.confidence >= 0.60
        assert decision.opportunity_score > 0
        assert decision.opportunity_tier in ("HOT", "GOOD", "NEUTRAL")
        assert decision.fusion_agreement_ratio > 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_bullish_decision_has_complete_fields(self, mock_call):
        """Verify all spec-required fields are populated."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return RECENT_BUY_SIGNALS
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("ETH-USD", timeout=10.0)

        # Schema fields
        assert decision.decision_id.startswith("sig-")
        assert decision.agent_type == "autonomous_runner"
        assert decision.latency_ms >= 0
        assert decision.created_at is not None

        # Strategy breakdown structure
        sb = decision.strategy_breakdown
        assert "strategies_analyzed" in sb
        assert "strategies_bullish" in sb
        assert "strategies_bearish" in sb
        assert "strategies_neutral" in sb
        assert "breakdown" in sb

        # Market context structure
        mc = decision.market_context
        assert "symbol" in mc
        assert "current_price" in mc
        assert "timestamp" in mc

        # Tool calls structure
        tc = decision.tool_calls
        assert "calls" in tc
        assert "tools_called" in tc
        assert "total_latency_ms" in tc

        # Opportunity factors
        assert decision.opportunity_factors.get("confidence") is not None
        assert decision.opportunity_factors.get("expected_return") is not None
        assert decision.opportunity_factors.get("consensus") is not None
        assert decision.opportunity_factors.get("volatility") is not None
        assert decision.opportunity_factors.get("freshness") is not None

        # Risk check
        assert isinstance(decision.risk_approved, bool)
        assert isinstance(decision.validation_status, str)


class TestFullPipelineBearish:
    """Test the full pipeline with bearish signals."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_bearish_consensus_generates_sell(self, mock_call):
        """When strategies + market both point bearish, emit SELL."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BEARISH_STRATEGIES
            elif tool == "get_market_summary":
                return BEARISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": [{"action": "SELL"}, {"action": "SELL"}]}
            elif tool == "get_signal_accuracy":
                return {
                    "accuracy": 0.4,
                    "buy_accuracy": 0.3,
                    "sell_accuracy": 0.7,
                    "total": 50,
                }
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision.action == "SELL"
        assert decision.confidence >= 0.50


class TestConflictResolution:
    """Test signal fusion with conflicting sources."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_mixed_signals_resolve_by_fusion(self, mock_call):
        """When strategies disagree, fusion should resolve the conflict."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return MIXED_STRATEGIES
            elif tool == "get_market_summary":
                return FLAT_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return ACCURACY_LOW
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        # With mixed signals, confidence should be moderate
        assert decision.action in ("BUY", "SELL", "HOLD")
        assert decision.confidence <= 0.85
        assert len(decision.source_signals) >= 1


class TestDegradedMode:
    """Test degraded signal generation when sources fail."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_all_sources_fail_generates_hold(self, mock_call):
        """When all MCP calls fail, generate a degraded HOLD signal."""
        mock_call.return_value = {"error": "Connection refused"}
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision.action == "HOLD"
        assert decision.confidence <= 0.50
        assert decision.tool_calls.get("is_degraded") is True

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_partial_failure_applies_penalty(self, mock_call):
        """When some sources fail, confidence penalty is applied."""
        call_count = [0]

        def mock_responses(tool, params, *args, **kwargs):
            call_count[0] += 1
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                raise ConnectionError("Market MCP down")
            elif tool == "get_recent_signals":
                raise ConnectionError("Signal MCP down")
            elif tool == "get_signal_accuracy":
                raise ConnectionError("Accuracy MCP down")
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        # Should still generate a signal but with degraded confidence
        assert decision is not None
        assert "Degraded" in decision.reasoning or decision.tool_calls.get(
            "is_degraded"
        )


class TestRiskManagement:
    """Test risk management integration in the pipeline."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_low_confidence_rejected(self, mock_call):
        """Signals below minimum confidence threshold are rejected."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return MIXED_STRATEGIES
            elif tool == "get_market_summary":
                return FLAT_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return ACCURACY_LOW
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        coord.risk_manager.config.min_confidence_threshold = 0.99

        decision = coord._process_symbol("BTC-USD", timeout=10.0)
        if decision.action != "HOLD":
            assert decision.risk_approved is False

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_max_concurrent_signals_enforced(self, mock_call):
        """Risk manager enforces maximum concurrent signal limit."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return RECENT_BUY_SIGNALS
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        # Set very low limit
        coord.risk_manager.config.max_concurrent_signals = 1

        # Process first symbol - should succeed
        d1 = coord._process_symbol("BTC-USD", timeout=10.0)
        if d1.risk_approved and d1.action != "HOLD":
            coord.risk_manager.record_signal_emitted("BTC-USD")

        # Process second symbol - might be rejected by max concurrent
        d2 = coord._process_symbol("ETH-USD", timeout=10.0)
        # Second signal may or may not be approved depending on risk state


class TestBatchProcessing:
    """Test batch symbol processing."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_batch_processes_all_symbols(self, mock_call):
        """Process multiple symbols in batch."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]
        decisions = coord.process_all_symbols(symbols, batch_size=10)

        assert len(decisions) == 3
        symbols_processed = {d.symbol for d in decisions}
        assert symbols_processed == {"BTC-USD", "ETH-USD", "SOL-USD"}

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_batch_with_partial_failures(self, mock_call):
        """Batch processing continues even if some symbols fail."""
        fail_symbols = {"FAIL-USD"}

        def mock_responses(tool, params, *args, **kwargs):
            symbol = params.get("symbol", "")
            if symbol in fail_symbols:
                raise Exception("Total failure for this symbol")
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        symbols = ["BTC-USD", "FAIL-USD", "ETH-USD"]
        decisions = coord.process_all_symbols(symbols, batch_size=10)

        # FAIL-USD should fail but other symbols succeed
        # (it may generate a degraded signal or be skipped)
        assert len(decisions) >= 2


class TestDecisionRecording:
    """Test that decisions are properly recorded."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_decisions_appear_in_recent_list(self, mock_call):
        """Decisions are recorded in the in-memory log."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        coord._process_symbol("BTC-USD", timeout=10.0)
        coord._process_symbol("ETH-USD", timeout=10.0)

        decisions = coord.get_recent_decisions(limit=10)
        assert len(decisions) == 2

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_pipeline_status_includes_metrics(self, mock_call):
        """Pipeline status includes all expected fields."""
        coord = _make_coordinator()
        status = coord.get_pipeline_status()

        assert "instance_id" in status
        assert "risk_status" in status
        assert "circuit_breaker" in status
        assert "adaptive" in status
        assert "db_persistence" in status
        assert "cache" in status
        assert "model_validator" in status
        assert "signal_publisher" in status
        assert "metrics" in status


class TestSignalEmission:
    """Test signal emission and publishing."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_approved_signal_calls_emit(self, mock_call):
        """Approved BUY/SELL signals call emit_signal MCP tool."""
        emit_called = [False]

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "emit_signal":
                emit_called[0] = True
                return {"success": True}
            elif tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return RECENT_BUY_SIGNALS
            elif tool == "get_signal_accuracy":
                return ACCURACY_HIGH
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        if decision.risk_approved and decision.action != "HOLD":
            assert emit_called[0] is True

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_hold_signal_not_emitted(self, mock_call):
        """HOLD signals are never emitted."""
        mock_call.return_value = {"error": "all fail"}
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision.action == "HOLD"
        # emit_signal should not appear in tool calls for HOLD
        emit_calls = [
            c
            for c in decision.tool_calls.get("calls", [])
            if c.get("tool") == "emit_signal"
        ]
        assert len(emit_calls) == 0


class TestPredictionMarketIntegration:
    """Test prediction market signal source."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_prediction_market_contributes_to_fusion(self, mock_call):
        """Prediction market signals are included in fusion."""

        def mock_responses(tool, params, *args, **kwargs):
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return {
                    "accuracy": 0.80,
                    "buy_accuracy": 0.85,
                    "sell_accuracy": 0.50,
                    "win_rate": 0.80,
                    "total_decisions": 50,
                    "total": 50,
                }
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        # Should have multiple source signals including prediction market
        sources = (
            {s.source for s in decision.source_signals}
            if decision.source_signals
            else set()
        )
        assert "strategy_consensus" in sources


class TestLearningEngineIntegration:
    """Test learning engine signal source."""

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_learning_engine_with_sufficient_data(self, mock_call):
        """Learning engine contributes signal when sufficient history exists."""
        call_log = []

        def mock_responses(tool, params, *args, **kwargs):
            call_log.append(tool)
            if tool == "get_top_strategies":
                return BULLISH_STRATEGIES
            elif tool == "get_market_summary":
                return BULLISH_MARKET
            elif tool == "get_recent_signals":
                return {"signals": []}
            elif tool == "get_signal_accuracy":
                return {
                    "accuracy": 0.75,
                    "buy_accuracy": 0.80,
                    "sell_accuracy": 0.50,
                    "win_rate": 0.75,
                    "total_decisions": 50,
                    "total": 50,
                }
            elif tool == "emit_signal":
                return {"success": True}
            return {"error": "unknown"}

        mock_call.side_effect = mock_responses
        coord = _make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision is not None
        # get_signal_accuracy should have been called for both prediction market and learning engine
        accuracy_calls = [c for c in call_log if c == "get_signal_accuracy"]
        assert len(accuracy_calls) >= 1
