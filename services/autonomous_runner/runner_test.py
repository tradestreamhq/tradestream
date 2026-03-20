"""Tests for the autonomous runner event loop."""

import threading
import time
from unittest.mock import MagicMock, patch

from services.autonomous_runner.config import Config
from services.autonomous_runner.runner import AutonomousRunner


def _make_config(**overrides):
    defaults = dict(
        mcp_strategy_url="http://localhost:8080",
        mcp_market_url="http://localhost:8081",
        mcp_signal_url="http://localhost:8082",
        schedule="*/1 * * * *",
        symbols=["BTC-USD"],
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestAutonomousRunner:
    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_creates_with_defaults(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        assert runner.instance_id is not None
        assert runner._shutdown.is_set() is False
        assert runner._consecutive_overruns == 0
        assert runner._cooldown_remaining == 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_shutdown_sets_event(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        runner.shutdown()
        assert runner._shutdown.is_set()

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_run_cycle_with_kill_switch_active(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        mock_ks = MagicMock()
        mock_ks.is_active.return_value = True
        runner._kill_switch = mock_ks

        runner._run_cycle()
        # Coordinator should NOT have been called
        mock_call.assert_not_called()

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_run_cycle_with_backpressure_cooldown(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        runner._cooldown_remaining = 3

        runner._run_cycle()
        assert runner._cooldown_remaining == 2
        mock_call.assert_not_called()

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_run_cycle_with_circuit_breaker_open(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        runner.coordinator.llm_circuit_breaker.allow_request = MagicMock(
            return_value=False
        )

        runner._run_cycle()
        mock_call.assert_not_called()

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_run_cycle_success(self, mock_call):
        """Successful cycle resets consecutive overruns."""
        mock_call.side_effect = _mock_mcp
        config = _make_config()
        runner = AutonomousRunner(config)
        runner._consecutive_overruns = 2

        runner._run_cycle()
        assert runner._consecutive_overruns == 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_run_cycle_failure_increments_overruns(self, mock_call):
        """Failed cycle increments overrun counter."""
        config = _make_config()
        runner = AutonomousRunner(config)
        runner.coordinator.process_all_symbols = MagicMock(
            side_effect=RuntimeError("boom")
        )

        runner._run_cycle()
        assert runner._consecutive_overruns == 1

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_backpressure_triggered_after_max_overruns(self, mock_call):
        """Backpressure triggers after max consecutive overruns."""
        config = _make_config()
        runner = AutonomousRunner(config)
        runner.coordinator.process_all_symbols = MagicMock(
            side_effect=RuntimeError("boom")
        )
        runner._consecutive_overruns = (
            config.adaptive.backpressure_max_overruns - 1
        )

        runner._run_cycle()
        assert runner._cooldown_remaining == config.adaptive.cooldown_cycles
        assert runner._consecutive_overruns == 0

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_start_shuts_down_on_event(self, mock_call):
        """Runner exits its loop when shutdown event is set."""
        config = _make_config()
        runner = AutonomousRunner(config)

        def stop_soon():
            time.sleep(0.1)
            runner.shutdown()

        t = threading.Thread(target=stop_soon)
        t.start()

        # Patch sleep to be instant so loop exits quickly
        with patch("time.sleep", return_value=None):
            runner.start()

        t.join(timeout=2)
        assert runner._shutdown.is_set()

    @patch("services.autonomous_runner.coordinator.resolve_and_call")
    def test_handle_shutdown_signal(self, mock_call):
        config = _make_config()
        runner = AutonomousRunner(config)
        runner._handle_shutdown(2, None)
        assert runner._shutdown.is_set()


def _mock_mcp(tool_name, arguments, *args, **kwargs):
    if tool_name == "get_top_strategies":
        return {
            "strategies": [
                {"name": "RSI", "signal": "BUY", "score": 0.85, "confidence": 0.8},
            ]
        }
    elif tool_name == "get_market_summary":
        return {"current_price": 65000.0, "price_change_1h": 1.5, "volume_ratio": 1.2}
    elif tool_name == "get_recent_signals":
        return {"signals": []}
    elif tool_name == "emit_signal":
        return {"success": True}
    return {"error": f"Unknown tool: {tool_name}"}
