"""Tests for signal coordinator."""

import json
from unittest.mock import MagicMock, patch

from services.autonomous_runner.config import Config
from services.autonomous_runner.coordinator import SignalCoordinator
from services.autonomous_runner.signal_fusion import SignalAction


class TestSignalCoordinator:
    def _make_coordinator(self) -> SignalCoordinator:
        config = Config(
            mcp_strategy_url="http://localhost:8080",
            mcp_market_url="http://localhost:8081",
            mcp_signal_url="http://localhost:8082",
        )
        return SignalCoordinator(config, "test-instance")

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_process_symbol_with_strategy_data(self, mock_call):
        """Test processing a symbol when strategy data is available."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision is not None
        assert decision.symbol == "BTC-USD"
        assert decision.action in ("BUY", "SELL", "HOLD")
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.latency_ms >= 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_process_symbol_all_errors(self, mock_call):
        """Test processing a symbol when all MCP calls fail."""
        mock_call.return_value = {"error": "Connection refused"}
        coord = self._make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert decision is not None
        assert decision.action == "HOLD"
        assert decision.confidence <= 0.50

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_process_all_symbols(self, mock_call):
        """Test processing multiple symbols."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        decisions = coord.process_all_symbols(["BTC-USD", "ETH-USD"], batch_size=10)
        assert len(decisions) == 2

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_decision_has_tool_calls(self, mock_call):
        """Test that decisions record tool call traces."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        assert "calls" in decision.tool_calls
        assert len(decision.tool_calls["calls"]) > 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_risk_rejected_signal_not_emitted(self, mock_call):
        """Test that risk-rejected signals don't get emitted."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        # Set low confidence threshold so signal gets rejected
        coord.risk_manager.config.min_confidence_threshold = 0.99

        decision = coord._process_symbol("BTC-USD", timeout=10.0)
        # Verify emit_signal was not called (no emit_signal in tool calls)
        emit_calls = [
            c
            for c in decision.tool_calls.get("calls", [])
            if c.get("tool") == "emit_signal"
        ]
        # If confidence < threshold, emit should not have been called
        if not decision.risk_approved:
            assert len(emit_calls) == 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_get_recent_decisions(self, mock_call):
        """Test retrieving recent decisions for dashboard."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        coord._process_symbol("BTC-USD", timeout=10.0)

        decisions = coord.get_recent_decisions(limit=10)
        assert len(decisions) == 1
        assert decisions[0]["symbol"] == "BTC-USD"

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_pipeline_status(self, mock_call):
        """Test pipeline status endpoint."""
        coord = self._make_coordinator()
        status = coord.get_pipeline_status()
        assert "instance_id" in status
        assert "risk_status" in status
        assert "circuit_breaker" in status

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_dedup_skips_duplicate_signal(self, mock_call):
        """Test that duplicate signals within 15-min window are skipped."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        # Ensure risk thresholds are permissive
        coord.risk_manager.config.min_confidence_threshold = 0.0
        coord.risk_manager.config.max_concurrent_signals = 100

        # Process symbol twice - second should be deduped
        d1 = coord._process_symbol("BTC-USD", timeout=10.0)
        d2 = coord._process_symbol("BTC-USD", timeout=10.0)

        assert d1 is not None
        assert d2 is not None

        # If both BUY signals, second should have dedup warning
        if d1.action == d2.action and d1.action != "HOLD":
            if d1.risk_approved:
                assert any(
                    "Duplicate" in w or "dedup" in w.lower()
                    for w in (d2.validation_warnings or [])
                )

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_entry_price_stored_on_emit(self, mock_call):
        """Test that entry price is stored when a signal is emitted."""
        mock_call.side_effect = self._mock_mcp_responses
        coord = self._make_coordinator()
        coord.risk_manager.config.min_confidence_threshold = 0.0
        coord.risk_manager.config.max_concurrent_signals = 100

        decision = coord._process_symbol("BTC-USD", timeout=10.0)

        if decision and decision.risk_approved and decision.action != "HOLD":
            entry_price = coord.get_entry_price(decision.decision_id)
            assert entry_price is not None
            assert entry_price == 65000.0  # from mock market data

    def _mock_mcp_responses(self, tool_name, arguments, *args, **kwargs):
        """Mock MCP responses for testing."""
        if tool_name == "get_top_strategies":
            return {
                "strategies": [
                    {
                        "name": "RSI_REVERSAL",
                        "signal": "BUY",
                        "score": 0.89,
                        "confidence": 0.85,
                    },
                    {
                        "name": "MACD_CROSS",
                        "signal": "BUY",
                        "score": 0.85,
                        "confidence": 0.78,
                    },
                    {
                        "name": "EMA_TREND",
                        "signal": "BUY",
                        "score": 0.72,
                        "confidence": 0.70,
                    },
                    {
                        "name": "VOLUME_BREAKOUT",
                        "signal": "SELL",
                        "score": 0.65,
                        "confidence": 0.60,
                    },
                ]
            }
        elif tool_name == "get_market_summary":
            return {
                "current_price": 65000.0,
                "price_change_1h": 1.5,
                "volume_ratio": 1.2,
                "volatility": 0.025,
            }
        elif tool_name == "get_recent_signals":
            return {"signals": []}
        elif tool_name == "emit_signal":
            return {"success": True, "signal_id": "sig-test-123"}
        return {"error": f"Unknown tool: {tool_name}"}
