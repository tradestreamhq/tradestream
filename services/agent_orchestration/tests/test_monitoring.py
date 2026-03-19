"""Tests for the monitoring phase."""

import os
import tempfile
from unittest.mock import patch

from services.agent_orchestration import config
from services.agent_orchestration.monitoring import monitor_promoted_strategies
from services.agent_orchestration.state import OrchestrationState


class TestMonitorPromotedStrategies:
    def _make_state_with_promoted(self, strategies):
        """Create a state with pre-promoted strategies."""
        tmp = tempfile.mkdtemp()
        state = OrchestrationState(state_file=os.path.join(tmp, "state.json"))
        state.cycle_number = 5
        for name, allocation in strategies:
            state.add_candidate(name, {})
            state.promote(name, allocation)
        return state

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    @patch("services.agent_orchestration.monitoring._log_monitoring_decision")
    def test_retires_bad_performer(self, mock_log, mock_metrics):
        state = self._make_state_with_promoted([("bad_strat", 0.1)])
        mock_metrics.return_value = {"sharpe_ratio": -0.5}
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        assert "bad_strat" in result["retired"]
        assert "bad_strat" not in state.candidates

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    @patch("services.agent_orchestration.monitoring._log_monitoring_decision")
    def test_increases_allocation_for_winner(self, mock_log, mock_metrics):
        state = self._make_state_with_promoted([("winner", 0.1)])
        mock_metrics.return_value = {"sharpe_ratio": 1.0}
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        assert len(result["adjusted"]) == 1
        adj = result["adjusted"][0]
        assert adj["new_allocation"] > adj["old_allocation"]

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    @patch("services.agent_orchestration.monitoring._log_monitoring_decision")
    def test_decreases_allocation_for_underperformer(self, mock_log, mock_metrics):
        state = self._make_state_with_promoted([("mediocre", 0.15)])
        mock_metrics.return_value = {"sharpe_ratio": 0.2}
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        assert len(result["adjusted"]) == 1
        adj = result["adjusted"][0]
        assert adj["new_allocation"] < adj["old_allocation"]

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    def test_no_promoted_strategies(self, mock_metrics):
        tmp = tempfile.mkdtemp()
        state = OrchestrationState(state_file=os.path.join(tmp, "state.json"))
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        assert result == {"adjusted": [], "retired": []}
        mock_metrics.assert_not_called()

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    def test_handles_missing_metrics(self, mock_metrics):
        state = self._make_state_with_promoted([("no_data", 0.1)])
        mock_metrics.return_value = None
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        assert len(result["adjusted"]) == 0
        assert len(result["retired"]) == 0

    @patch("services.agent_orchestration.monitoring._get_live_metrics")
    @patch("services.agent_orchestration.monitoring._log_monitoring_decision")
    def test_allocation_capped_at_max(self, mock_log, mock_metrics):
        state = self._make_state_with_promoted([("winner", 0.24)])
        mock_metrics.return_value = {"sharpe_ratio": 1.5}
        mcp_urls = {"signal": "http://localhost:8082"}

        result = monitor_promoted_strategies(state, mcp_urls)
        if result["adjusted"]:
            assert (
                result["adjusted"][0]["new_allocation"] <= config.MAX_ALLOCATION_WEIGHT
            )
