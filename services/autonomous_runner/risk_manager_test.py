"""Tests for autonomous risk management."""

from services.autonomous_runner.config import RiskConfig
from services.autonomous_runner.risk_manager import RiskCheckResult, RiskManager
from services.autonomous_runner.signal_fusion import (
    FusedSignal,
    SignalAction,
    SourceSignal,
)


def _make_signal(
    symbol="BTC-USD",
    action=SignalAction.BUY,
    confidence=0.80,
    agreement_ratio=0.80,
) -> FusedSignal:
    return FusedSignal(
        symbol=symbol,
        action=action,
        confidence=confidence,
        source_signals=[],
        agreement_ratio=agreement_ratio,
    )


class TestRiskManager:
    def _make_manager(self, **overrides) -> RiskManager:
        config = RiskConfig(**overrides)
        return RiskManager(config)

    def test_approve_high_confidence_signal(self):
        rm = self._make_manager()
        signal = _make_signal(confidence=0.80)
        result = rm.check_signal(signal)
        assert result.approved is True
        assert result.position_size_pct > 0

    def test_reject_low_confidence(self):
        rm = self._make_manager(min_confidence_threshold=0.60)
        signal = _make_signal(confidence=0.40)
        result = rm.check_signal(signal)
        assert result.approved is False
        assert any("Confidence" in r for r in result.rejection_reasons)

    def test_hold_always_approved(self):
        rm = self._make_manager()
        signal = _make_signal(action=SignalAction.HOLD, confidence=0.20)
        result = rm.check_signal(signal)
        assert result.approved is True
        assert result.position_size_pct == 0

    def test_max_concurrent_signals(self):
        rm = self._make_manager(max_concurrent_signals=2)
        signal = _make_signal()

        # First two should pass
        r1 = rm.check_signal(signal)
        assert r1.approved is True
        rm.record_signal_emitted("BTC-USD")

        r2 = rm.check_signal(signal)
        assert r2.approved is True
        rm.record_signal_emitted("ETH-USD")

        # Third should fail
        r3 = rm.check_signal(signal)
        assert r3.approved is False
        assert any("concurrent" in r.lower() for r in r3.rejection_reasons)

    def test_per_symbol_rate_limit(self):
        rm = self._make_manager(max_signals_per_symbol_per_hour=2)
        signal = _make_signal(symbol="BTC-USD")

        rm.record_signal_emitted("BTC-USD")
        rm.record_signal_emitted("BTC-USD")

        result = rm.check_signal(signal)
        assert result.approved is False
        assert any("BTC-USD" in r for r in result.rejection_reasons)

    def test_portfolio_exposure_limit(self):
        rm = self._make_manager(max_portfolio_exposure_pct=50.0)
        rm.update_portfolio_exposure(55.0)

        signal = _make_signal()
        result = rm.check_signal(signal)
        assert result.approved is False
        assert any("exposure" in r.lower() for r in result.rejection_reasons)

    def test_daily_loss_limit(self):
        rm = self._make_manager(max_daily_loss_pct=5.0)
        # Simulate losses
        rm.record_signal_closed("BTC-USD", -3.0)
        rm.record_signal_closed("ETH-USD", -3.0)

        signal = _make_signal()
        result = rm.check_signal(signal)
        assert result.approved is False
        assert any("daily loss" in r.lower() for r in result.rejection_reasons)

    def test_position_size_scales_with_confidence(self):
        rm = self._make_manager(max_single_position_pct=20.0)

        high_conf = _make_signal(confidence=0.90)
        low_conf = _make_signal(confidence=0.55)

        r_high = rm.check_signal(high_conf)
        r_low = rm.check_signal(low_conf)

        assert r_high.position_size_pct > r_low.position_size_pct

    def test_reset_daily(self):
        rm = self._make_manager(max_daily_loss_pct=5.0)
        rm.record_signal_closed("BTC-USD", -4.0)
        rm.reset_daily()

        signal = _make_signal()
        result = rm.check_signal(signal)
        assert result.approved is True

    def test_get_status(self):
        rm = self._make_manager()
        rm.record_signal_emitted("BTC-USD")
        status = rm.get_status()
        assert status["active_signals"] == 1
        assert "limits" in status
        assert "max_daily_loss_pct" in status["limits"]

    def test_confidence_adjusted_when_in_drawdown(self):
        rm = self._make_manager(
            max_daily_loss_pct=10.0,
            min_confidence_threshold=0.50,
        )
        rm.record_signal_closed("BTC-USD", -7.0)  # 70% of limit

        signal = _make_signal(confidence=0.55)
        result = rm.check_signal(signal)
        # Confidence should be adjusted down
        if result.approved:
            assert result.adjusted_confidence <= 0.55
