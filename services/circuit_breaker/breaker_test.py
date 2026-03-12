"""Tests for the circuit breaker core logic."""

import pytest

from services.circuit_breaker.breaker import CircuitBreaker
from services.circuit_breaker.models import BreakerLevel, ThresholdConfig


class TestThresholdConfig:
    def test_default_thresholds(self):
        cfg = ThresholdConfig()
        assert cfg.warning == 0.05
        assert cfg.halt == 0.10
        assert cfg.emergency == 0.20

    def test_custom_thresholds(self):
        cfg = ThresholdConfig(warning=0.03, halt=0.07, emergency=0.15)
        assert cfg.warning == 0.03

    def test_invalid_order_raises(self):
        with pytest.raises(ValueError):
            ThresholdConfig(warning=0.10, halt=0.05, emergency=0.20)

    def test_zero_warning_raises(self):
        with pytest.raises(ValueError):
            ThresholdConfig(warning=0.0, halt=0.10, emergency=0.20)


class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        state = cb.state
        assert state.level == BreakerLevel.NORMAL
        assert state.is_halted is False
        assert cb.is_trading_allowed() is True

    def test_peak_tracking(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        assert cb.state.peak_equity == 10000.0
        cb.update_equity(10500.0)
        assert cb.state.peak_equity == 10500.0
        cb.update_equity(10200.0)
        assert cb.state.peak_equity == 10500.0

    def test_warning_threshold(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        # 5% drawdown -> warning
        cb.update_equity(9500.0)
        state = cb.state
        assert state.level == BreakerLevel.WARNING
        assert state.is_halted is False
        assert cb.is_trading_allowed() is True

    def test_halt_threshold(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        # 10% drawdown -> halt
        cb.update_equity(9000.0, strategies=["MACD_CROSSOVER", "SMA_RSI"])
        state = cb.state
        assert state.level == BreakerLevel.HALT
        assert state.is_halted is True
        assert cb.is_trading_allowed() is False
        assert "MACD_CROSSOVER" in state.halted_strategies

    def test_emergency_threshold(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        # 20% drawdown -> emergency
        cb.update_equity(8000.0, strategies=["STRAT_A"])
        state = cb.state
        assert state.level == BreakerLevel.EMERGENCY
        assert state.is_halted is True

    def test_reset_after_halt(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        cb.update_equity(9000.0, strategies=["STRAT_A"])
        assert cb.is_trading_allowed() is False

        success = cb.reset("admin@tradestream.io")
        assert success is True
        assert cb.is_trading_allowed() is True
        assert cb.state.level == BreakerLevel.NORMAL
        assert cb.state.reset_acknowledged is True

    def test_reset_when_not_halted_returns_false(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        assert cb.reset("admin") is False

    def test_callback_on_trigger(self):
        events = []
        cb = CircuitBreaker(on_trigger=lambda e: events.append(e))
        cb.update_equity(10000.0)
        cb.update_equity(9000.0)
        assert len(events) >= 1
        assert events[-1].level == BreakerLevel.HALT

    def test_warning_clears_on_recovery(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        cb.update_equity(9500.0)
        assert cb.state.level == BreakerLevel.WARNING
        # Recover above warning threshold
        cb.update_equity(9600.0)
        assert cb.state.level == BreakerLevel.NORMAL

    def test_halt_does_not_clear_on_recovery(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        cb.update_equity(9000.0)
        assert cb.state.is_halted is True
        # Even if equity recovers, halt remains until manual reset
        cb.update_equity(9800.0)
        assert cb.state.is_halted is True

    def test_events_are_recorded(self):
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        cb.update_equity(9500.0)  # warning
        cb.update_equity(9000.0)  # halt
        events = cb.state.events
        assert len(events) == 2
        assert events[0].level == BreakerLevel.WARNING
        assert events[1].level == BreakerLevel.HALT

    def test_zero_equity_does_not_crash(self):
        cb = CircuitBreaker()
        cb.update_equity(0.0)
        assert cb.state.level == BreakerLevel.NORMAL

    def test_escalation_skips_warning(self):
        """Direct jump from NORMAL to HALT if drawdown exceeds halt threshold."""
        cb = CircuitBreaker()
        cb.update_equity(10000.0)
        cb.update_equity(8500.0)  # 15% drawdown, skips warning to halt
        state = cb.state
        assert state.level == BreakerLevel.HALT
        assert state.is_halted is True
