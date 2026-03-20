"""Tests for orchestration state persistence."""

import json
import os
import tempfile

from services.agent_orchestration import config
from services.agent_orchestration.state import CandidateRecord, OrchestrationState


class TestCandidateRecord:
    def test_to_dict_roundtrip(self):
        rec = CandidateRecord(
            name="test_strategy",
            spec={"indicators": {"RSI": {"period": 14}}},
            phase=config.PHASE_VALIDATION,
            metrics={"sharpe_ratio": 1.5},
            allocation_weight=0.1,
        )
        d = rec.to_dict()
        restored = CandidateRecord.from_dict(d)
        assert restored.name == rec.name
        assert restored.spec == rec.spec
        assert restored.phase == rec.phase
        assert restored.metrics == rec.metrics
        assert restored.allocation_weight == rec.allocation_weight

    def test_defaults(self):
        rec = CandidateRecord(name="x", spec={})
        assert rec.phase == config.PHASE_DISCOVERY
        assert rec.metrics == {}
        assert rec.allocation_weight == 0.0
        assert rec.created_at > 0


class TestOrchestrationState:
    def _make_state(self, tmp_dir):
        path = os.path.join(tmp_dir, "state.json")
        return OrchestrationState(state_file=path)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = self._make_state(tmp_dir)
            state.cycle_number = 5
            state.add_candidate("strat_a", {"source": "test"})
            state.advance_to_validation("strat_a", {"sharpe_ratio": 1.2})
            state.promote("strat_a", 0.1)
            state.save()

            state2 = self._make_state(tmp_dir)
            state2.state_file = state.state_file
            state2.load()

            assert state2.cycle_number == 5
            assert "strat_a" in state2.candidates
            assert state2.candidates["strat_a"].phase == config.PHASE_PROMOTION
            assert state2.candidates["strat_a"].allocation_weight == 0.1
            assert len(state2.promotion_history) == 1

    def test_add_and_advance(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = self._make_state(tmp_dir)
            state.add_candidate("s1", {"ind": "RSI"})
            assert state.candidates["s1"].phase == config.PHASE_DISCOVERY

            state.advance_to_validation("s1", {"sharpe_ratio": 0.8})
            assert state.candidates["s1"].phase == config.PHASE_VALIDATION
            assert state.candidates["s1"].metrics["sharpe_ratio"] == 0.8

    def test_promote_and_retire(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = self._make_state(tmp_dir)
            state.cycle_number = 1
            state.add_candidate("s1", {})
            state.promote("s1", 0.05)
            assert len(state.promotion_history) == 1
            assert state.candidates["s1"].phase == config.PHASE_PROMOTION

            state.retire("s1", "bad performance")
            assert "s1" not in state.candidates
            assert len(state.retirement_history) == 1
            assert state.retirement_history[0]["reason"] == "bad performance"

    def test_get_candidates_in_phase(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = self._make_state(tmp_dir)
            state.add_candidate("a", {})
            state.add_candidate("b", {})
            state.promote("b", 0.1)

            discovery = state.get_candidates_in_phase(config.PHASE_DISCOVERY)
            promoted = state.get_promoted_strategies()
            assert len(discovery) == 1
            assert discovery[0].name == "a"
            assert len(promoted) == 1
            assert promoted[0].name == "b"

    def test_record_cycle_stats(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = self._make_state(tmp_dir)
            state.cycle_number = 1
            state.record_cycle_stats({"discovered": 5, "promoted": 1})
            assert len(state.cycle_stats) == 1
            assert state.cycle_stats[0]["cycle"] == 1
            assert state.cycle_stats[0]["discovered"] == 5

    def test_load_missing_file(self):
        state = OrchestrationState(state_file="/tmp/nonexistent_test_state_12345.json")
        state.load()  # Should not raise
        assert state.cycle_number == 0

    def test_load_corrupt_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{{{")
            path = f.name
        try:
            state = OrchestrationState(state_file=path)
            state.load()  # Should not raise
            assert state.cycle_number == 0
        finally:
            os.unlink(path)
