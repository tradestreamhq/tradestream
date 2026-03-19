"""Tests for the main orchestration loop."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from services.agent_orchestration import config
from services.agent_orchestration.orchestration_loop import run_cycle
from services.agent_orchestration.state import OrchestrationState


class TestRunCycle:
    def _make_state(self):
        tmp = tempfile.mkdtemp()
        return OrchestrationState(state_file=os.path.join(tmp, "state.json"))

    @patch("services.agent_orchestration.orchestration_loop.monitor_promoted_strategies")
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_full_cycle(self, mock_discover, mock_validate, mock_promote, mock_monitor):
        mock_discover.return_value = ["strat_a", "strat_b"]
        mock_validate.return_value = [
            ("strat_a", {"sharpe_ratio": 1.5, "win_rate": 0.6}),
        ]
        mock_promote.return_value = ["strat_a"]
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        state = self._make_state()
        mcp_urls = {
            "strategy": "http://localhost:8080",
            "signal": "http://localhost:8082",
            "backtest": "http://localhost:8083",
        }

        stats = run_cycle("test-key", mcp_urls, state)

        assert stats["discovered"] == 2
        assert stats["validated"] == 1
        assert stats["promoted"] == 1
        assert state.cycle_number == 1
        assert len(state.cycle_stats) == 1
        mock_discover.assert_called_once_with("test-key", mcp_urls)
        mock_validate.assert_called_once_with(["strat_a", "strat_b"], mcp_urls)

    @patch("services.agent_orchestration.orchestration_loop.monitor_promoted_strategies")
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_handles_discovery_failure(self, mock_discover, mock_validate,
                                       mock_promote, mock_monitor):
        mock_discover.side_effect = Exception("LLM unavailable")
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        state = self._make_state()
        mcp_urls = {"strategy": "http://localhost:8080"}

        stats = run_cycle("test-key", mcp_urls, state)

        assert stats["discovered"] == 0
        # Validation should still be called with empty list
        mock_validate.assert_called_once_with([], mcp_urls)

    @patch("services.agent_orchestration.orchestration_loop.monitor_promoted_strategies")
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_increments_cycle_number(self, mock_discover, mock_validate,
                                      mock_promote, mock_monitor):
        mock_discover.return_value = []
        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        state = self._make_state()
        state.cycle_number = 10
        mcp_urls = {}

        run_cycle("key", mcp_urls, state)
        assert state.cycle_number == 11

        run_cycle("key", mcp_urls, state)
        assert state.cycle_number == 12

    @patch("services.agent_orchestration.orchestration_loop.monitor_promoted_strategies")
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_persists_state_after_cycle(self, mock_discover, mock_validate,
                                         mock_promote, mock_monitor):
        mock_discover.return_value = ["s1"]
        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        state = self._make_state()
        mcp_urls = {}

        run_cycle("key", mcp_urls, state)

        # Verify state was saved
        assert os.path.exists(state.state_file)

        # Load a fresh state and verify
        state2 = OrchestrationState(state_file=state.state_file)
        state2.load()
        assert state2.cycle_number == 1
