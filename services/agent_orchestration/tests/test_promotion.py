"""Tests for the promotion phase."""

import tempfile
import os
from unittest.mock import patch

from services.agent_orchestration import config
from services.agent_orchestration.promotion import promote_winners
from services.agent_orchestration.state import OrchestrationState


class TestPromoteWinners:
    def _make_state(self):
        tmp = tempfile.mkdtemp()
        return OrchestrationState(state_file=os.path.join(tmp, "state.json"))

    @patch("services.agent_orchestration.promotion._log_promotion_decision")
    def test_promotes_top_candidates(self, mock_log):
        state = self._make_state()
        state.cycle_number = 1
        state.add_candidate("strat_a", {})
        state.add_candidate("strat_b", {})

        validated = [
            ("strat_a", {"sharpe_ratio": 2.0, "win_rate": 0.7}),
            ("strat_b", {"sharpe_ratio": 1.5, "win_rate": 0.6}),
        ]
        mcp_urls = {"signal": "http://localhost:8082"}

        promoted = promote_winners(validated, state, mcp_urls)
        assert len(promoted) == 2
        assert state.candidates["strat_a"].phase == config.PHASE_PROMOTION
        assert (
            state.candidates["strat_a"].allocation_weight
            == config.INITIAL_ALLOCATION_WEIGHT
        )
        assert len(state.promotion_history) == 2

    @patch("services.agent_orchestration.promotion._log_promotion_decision")
    def test_respects_max_promoted_per_cycle(self, mock_log):
        state = self._make_state()
        state.cycle_number = 1

        # Create more candidates than MAX_PROMOTED_PER_CYCLE
        candidates = []
        for i in range(5):
            name = f"strat_{i}"
            state.add_candidate(name, {})
            candidates.append((name, {"sharpe_ratio": 2.0 - i * 0.1, "win_rate": 0.6}))

        mcp_urls = {"signal": "http://localhost:8082"}
        promoted = promote_winners(candidates, state, mcp_urls)
        assert len(promoted) == config.MAX_PROMOTED_PER_CYCLE

    @patch("services.agent_orchestration.promotion._log_promotion_decision")
    def test_skips_already_promoted(self, mock_log):
        state = self._make_state()
        state.cycle_number = 1
        state.add_candidate("existing", {})
        state.promote("existing", 0.1)

        validated = [("existing", {"sharpe_ratio": 2.0, "win_rate": 0.7})]
        mcp_urls = {"signal": "http://localhost:8082"}

        promoted = promote_winners(validated, state, mcp_urls)
        assert len(promoted) == 0
