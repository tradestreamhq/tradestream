"""End-to-end test: Agent Orchestration.

Validates the orchestration cycle: trigger discovery → generate candidates →
validate via backtest → promote winners → monitor live strategies.

Uses mocked MCP calls and LLM responses to exercise the real orchestration
state machine and cycle logic.
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from services.agent_orchestration import config
from services.agent_orchestration.orchestration_loop import run_cycle
from services.agent_orchestration.resilience import CircuitBreaker
from services.agent_orchestration.state import CandidateRecord, OrchestrationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state():
    """Fresh OrchestrationState with a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        state_file = f.name
    s = OrchestrationState(state_file=state_file)
    yield s
    try:
        os.unlink(state_file)
    except FileNotFoundError:
        pass


@pytest.fixture
def circuit_breakers():
    """Circuit breakers for each MCP service."""
    return {
        "strategy": CircuitBreaker(name="strategy"),
        "backtest": CircuitBreaker(name="backtest"),
        "signal": CircuitBreaker(name="signal"),
    }


# ---------------------------------------------------------------------------
# State Management Tests
# ---------------------------------------------------------------------------


class TestOrchestrationStateE2E:
    """Test the orchestration state machine lifecycle."""

    def test_add_candidate_and_advance(self, state):
        """Candidate moves through discovery → validation → promotion phases."""
        state.add_candidate("ema_cross_btc", {"source": "discovery", "cycle": 1})

        assert "ema_cross_btc" in state.candidates
        assert state.candidates["ema_cross_btc"].phase == config.PHASE_DISCOVERY

        state.advance_to_validation("ema_cross_btc", {"sharpe": 1.5, "win_rate": 0.6})
        assert state.candidates["ema_cross_btc"].phase == config.PHASE_VALIDATION
        assert state.candidates["ema_cross_btc"].metrics["sharpe"] == 1.5

        state.promote("ema_cross_btc", allocation_weight=0.1)
        assert state.candidates["ema_cross_btc"].phase == config.PHASE_PROMOTION
        assert state.candidates["ema_cross_btc"].allocation_weight == 0.1
        assert len(state.promotion_history) == 1

    def test_retire_strategy(self, state):
        """Retired strategy is removed from candidates and logged."""
        state.add_candidate("bad_strat", {"source": "test"})
        state.promote("bad_strat", 0.05)
        state.retire("bad_strat", reason="sharpe below threshold")

        assert "bad_strat" not in state.candidates
        assert len(state.retirement_history) == 1
        assert state.retirement_history[0]["reason"] == "sharpe below threshold"

    def test_state_persistence(self, state):
        """State survives save → load cycle."""
        state.add_candidate("persist_strat", {"source": "test"})
        state.promote("persist_strat", 0.15)
        state.cycle_number = 5
        state.record_cycle_stats({"discovered": 3, "validated": 1, "promoted": 1})
        state.save()

        # Load into fresh state
        loaded = OrchestrationState(state_file=state.state_file)
        loaded.load()

        assert loaded.cycle_number == 5
        assert "persist_strat" in loaded.candidates
        assert loaded.candidates["persist_strat"].phase == config.PHASE_PROMOTION
        assert loaded.candidates["persist_strat"].allocation_weight == 0.15
        assert len(loaded.promotion_history) == 1
        assert len(loaded.cycle_stats) == 1

    def test_get_candidates_by_phase(self, state):
        """Filter candidates by phase works correctly."""
        state.add_candidate("disc-1", {"source": "discovery"})
        state.add_candidate("disc-2", {"source": "discovery"})
        state.add_candidate("val-1", {"source": "discovery"})
        state.advance_to_validation("val-1", {"sharpe": 1.0})

        discovery = state.get_candidates_in_phase(config.PHASE_DISCOVERY)
        validation = state.get_candidates_in_phase(config.PHASE_VALIDATION)

        assert len(discovery) == 2
        assert len(validation) == 1
        assert validation[0].name == "val-1"

    def test_promoted_strategies_query(self, state):
        """get_promoted_strategies returns only promoted candidates."""
        state.add_candidate("s1", {})
        state.add_candidate("s2", {})
        state.promote("s1", 0.1)

        promoted = state.get_promoted_strategies()
        assert len(promoted) == 1
        assert promoted[0].name == "s1"

    def test_cycle_stats_recorded(self, state):
        """Cycle stats include cycle number and timestamp."""
        state.cycle_number = 10
        stats = {"discovered": 5, "validated": 2, "promoted": 1}
        state.record_cycle_stats(stats)

        assert len(state.cycle_stats) == 1
        assert state.cycle_stats[0]["cycle"] == 10
        assert "timestamp" in state.cycle_stats[0]
        assert state.cycle_stats[0]["discovered"] == 5


# ---------------------------------------------------------------------------
# Orchestration Cycle Tests
# ---------------------------------------------------------------------------


class TestOrchestrationCycleE2E:
    """Test the full orchestration cycle with mocked service calls."""

    @patch(
        "services.agent_orchestration.orchestration_loop.monitor_promoted_strategies"
    )
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_full_cycle_happy_path(
        self, mock_discovery, mock_validate, mock_promote, mock_monitor, state
    ):
        """Complete cycle: discovery → validation → promotion → monitoring."""
        mock_discovery.return_value = ["ema_btc", "macd_eth"]
        mock_validate.return_value = [
            ("ema_btc", {"sharpe": 1.5, "win_rate": 0.6}),
        ]
        mock_promote.return_value = ["ema_btc"]
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        mcp_urls = {
            "strategy": "http://strategy:8080",
            "backtest": "http://backtest:8080",
        }
        stats = run_cycle("test-key", mcp_urls, state)

        assert stats["discovered"] == 2
        assert stats["validated"] == 1
        assert stats["promoted"] == 1
        assert state.cycle_number == 1
        assert "ema_btc" in state.candidates
        assert state.candidates["ema_btc"].phase == config.PHASE_VALIDATION

    @patch(
        "services.agent_orchestration.orchestration_loop.monitor_promoted_strategies"
    )
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_discovery_failure_doesnt_block_cycle(
        self, mock_discovery, mock_validate, mock_promote, mock_monitor, state
    ):
        """Discovery failure is caught; validation still runs (with empty input)."""
        mock_discovery.side_effect = ConnectionError("LLM unreachable")
        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        stats = run_cycle("key", {"strategy": "http://s:80"}, state)

        assert stats["discovered"] == 0
        assert state.cycle_number == 1
        mock_validate.assert_called_once()

    @patch(
        "services.agent_orchestration.orchestration_loop.monitor_promoted_strategies"
    )
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_circuit_breaker_skips_phase(
        self,
        mock_discovery,
        mock_validate,
        mock_promote,
        mock_monitor,
        state,
        circuit_breakers,
    ):
        """Open circuit breaker skips the corresponding phase."""
        # Trip the strategy circuit breaker
        cb = circuit_breakers["strategy"]
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            cb.record_failure()

        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        stats = run_cycle("key", {"strategy": "http://s:80"}, state, circuit_breakers)

        assert "discovery" in stats["skipped_phases"]
        mock_discovery.assert_not_called()

    @patch(
        "services.agent_orchestration.orchestration_loop.monitor_promoted_strategies"
    )
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_monitoring_retires_underperformers(
        self, mock_discovery, mock_validate, mock_promote, mock_monitor, state
    ):
        """Monitoring phase can report retired strategies."""
        mock_discovery.return_value = []
        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {
            "adjusted": [("strat-a", 0.15)],
            "retired": ["strat-b"],
        }

        # Pre-populate state
        state.add_candidate("strat-a", {})
        state.promote("strat-a", 0.1)
        state.add_candidate("strat-b", {})
        state.promote("strat-b", 0.05)

        stats = run_cycle("key", {"signal": "http://s:80"}, state)

        assert stats["monitored_adjusted"] == 1
        assert stats["monitored_retired"] == 1

    @patch(
        "services.agent_orchestration.orchestration_loop.monitor_promoted_strategies"
    )
    @patch("services.agent_orchestration.orchestration_loop.promote_winners")
    @patch("services.agent_orchestration.orchestration_loop.validate_candidates")
    @patch("services.agent_orchestration.orchestration_loop.run_discovery")
    def test_consecutive_cycles_increment_counter(
        self, mock_discovery, mock_validate, mock_promote, mock_monitor, state
    ):
        """Running multiple cycles increments the cycle counter."""
        mock_discovery.return_value = []
        mock_validate.return_value = []
        mock_promote.return_value = []
        mock_monitor.return_value = {"adjusted": [], "retired": []}

        mcp_urls = {"strategy": "http://s:80"}
        run_cycle("key", mcp_urls, state)
        run_cycle("key", mcp_urls, state)
        run_cycle("key", mcp_urls, state)

        assert state.cycle_number == 3
        assert len(state.cycle_stats) == 3


# ---------------------------------------------------------------------------
# Circuit Breaker Integration Tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerE2E:
    """Circuit breaker integration with orchestration."""

    def test_circuit_breaker_opens_after_failures(self):
        """CB opens after N consecutive failures."""
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)

        assert cb.allow_request() is True
        cb.record_failure()
        cb.record_failure()
        assert cb.allow_request() is True
        cb.record_failure()
        assert cb.allow_request() is False

    def test_circuit_breaker_resets_on_success(self):
        """Success resets the failure counter."""
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.allow_request() is True  # counter reset by success


# ---------------------------------------------------------------------------
# CandidateRecord Serialization Tests
# ---------------------------------------------------------------------------


class TestCandidateRecordSerialization:
    """CandidateRecord round-trips through dict serialization."""

    def test_round_trip(self):
        rec = CandidateRecord(
            name="test-strat",
            spec={"source": "discovery"},
            phase=config.PHASE_VALIDATION,
            metrics={"sharpe": 1.5},
            allocation_weight=0.1,
        )
        d = rec.to_dict()
        restored = CandidateRecord.from_dict(d)

        assert restored.name == "test-strat"
        assert restored.phase == config.PHASE_VALIDATION
        assert restored.metrics == {"sharpe": 1.5}
        assert restored.allocation_weight == 0.1
