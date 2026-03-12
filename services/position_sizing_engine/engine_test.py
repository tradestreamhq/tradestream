"""Tests for the position sizing engine core logic."""

import pytest

from services.position_sizing_engine.engine import (
    PortfolioConstraints,
    SizingMethod,
    SizingRequest,
    SizingResult,
    apply_portfolio_constraints,
    calculate_position_size,
)


def _make_request(**overrides) -> SizingRequest:
    defaults = dict(
        strategy_id="strat-1",
        signal_strength=1.0,
        entry_price=100.0,
        stop_loss_price=95.0,
        current_equity=100_000.0,
        max_position_pct=0.20,
        method=SizingMethod.FIXED_FRACTIONAL,
        risk_pct=0.02,
    )
    defaults.update(overrides)
    return SizingRequest(**defaults)


# ---------- Fixed Fractional ----------


class TestFixedFractional:
    def test_basic(self):
        req = _make_request()
        result = calculate_position_size(req)
        # risk_amount = 100_000 * 0.02 = 2_000
        # risk_per_share = 100 - 95 = 5
        # shares = 2_000 / 5 = 400
        assert result.shares == pytest.approx(400.0)
        assert result.dollar_amount == pytest.approx(40_000.0)
        assert result.risk_amount == pytest.approx(2_000.0)
        assert result.risk_pct == pytest.approx(0.02)
        assert result.method == SizingMethod.FIXED_FRACTIONAL

    def test_no_stop_loss_returns_zero(self):
        req = _make_request(stop_loss_price=None)
        result = calculate_position_size(req)
        assert result.shares == 0.0
        assert result.dollar_amount == 0.0

    def test_stop_equals_entry_returns_zero(self):
        req = _make_request(stop_loss_price=100.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_zero_equity_returns_zero(self):
        req = _make_request(current_equity=0.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_signal_strength_scales_result(self):
        full = calculate_position_size(_make_request(signal_strength=1.0))
        half = calculate_position_size(_make_request(signal_strength=0.5))
        assert half.shares == pytest.approx(full.shares * 0.5)
        assert half.dollar_amount == pytest.approx(full.dollar_amount * 0.5)

    def test_max_position_pct_caps_size(self):
        # risk_pct large enough to exceed 20% of equity
        req = _make_request(risk_pct=0.10, max_position_pct=0.10)
        result = calculate_position_size(req)
        max_dollar = 100_000 * 0.10
        assert result.dollar_amount <= max_dollar + 0.01
        assert result.constrained is True

    def test_short_position(self):
        # entry below stop loss (short trade)
        req = _make_request(entry_price=95.0, stop_loss_price=100.0)
        result = calculate_position_size(req)
        assert result.shares == pytest.approx(400.0)


# ---------- Kelly Criterion ----------


class TestKelly:
    def test_basic(self):
        req = _make_request(
            method=SizingMethod.KELLY_CRITERION,
            win_rate=0.6,
            payoff_ratio=1.5,
            kelly_fraction=0.5,
        )
        result = calculate_position_size(req)
        # kelly_f = (0.6 * 1.5 - 0.4) / 1.5 = 0.3333
        # half_kelly = 0.1667
        # dollar = 100_000 * 0.1667 = 16_667
        # shares = 16_667 / 100 = 166.67
        assert result.shares == pytest.approx(166.67, rel=0.01)
        assert result.dollar_amount == pytest.approx(16_666.67, rel=0.01)
        assert result.method == SizingMethod.KELLY_CRITERION

    def test_negative_edge_returns_zero(self):
        # win_rate too low for positive edge
        req = _make_request(
            method=SizingMethod.KELLY_CRITERION,
            win_rate=0.3,
            payoff_ratio=1.0,
        )
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_zero_payoff_returns_zero(self):
        req = _make_request(
            method=SizingMethod.KELLY_CRITERION,
            win_rate=0.6,
            payoff_ratio=0.0,
        )
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_defaults_without_win_rate(self):
        req = _make_request(method=SizingMethod.KELLY_CRITERION)
        result = calculate_position_size(req)
        # Defaults: win_rate=0.5, payoff_ratio=1.0
        # kelly_f = (0.5 * 1.0 - 0.5) / 1.0 = 0.0
        assert result.shares == 0.0


# ---------- Volatility-Adjusted ----------


class TestVolatilityAdjusted:
    def test_basic(self):
        req = _make_request(
            method=SizingMethod.VOLATILITY_ADJUSTED,
            atr=2.5,
            atr_multiplier=2.0,
        )
        result = calculate_position_size(req)
        # risk_amount = 100_000 * 0.02 = 2_000
        # risk_per_share = 2.0 * 2.5 = 5.0
        # shares = 2_000 / 5 = 400
        assert result.shares == pytest.approx(400.0)
        assert result.dollar_amount == pytest.approx(40_000.0)

    def test_no_atr_returns_zero(self):
        req = _make_request(method=SizingMethod.VOLATILITY_ADJUSTED, atr=None)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_zero_atr_returns_zero(self):
        req = _make_request(method=SizingMethod.VOLATILITY_ADJUSTED, atr=0.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_higher_atr_smaller_position(self):
        low_vol = calculate_position_size(
            _make_request(method=SizingMethod.VOLATILITY_ADJUSTED, atr=1.0)
        )
        high_vol = calculate_position_size(
            _make_request(method=SizingMethod.VOLATILITY_ADJUSTED, atr=5.0)
        )
        assert high_vol.shares < low_vol.shares


# ---------- Equal Weight ----------


class TestEqualWeight:
    def test_basic(self):
        req = _make_request(method=SizingMethod.EQUAL_WEIGHT, num_positions=10)
        result = calculate_position_size(req)
        # dollar = 100_000 / 10 = 10_000
        # shares = 10_000 / 100 = 100
        assert result.shares == pytest.approx(100.0)
        assert result.dollar_amount == pytest.approx(10_000.0)

    def test_risk_with_stop_loss(self):
        req = _make_request(
            method=SizingMethod.EQUAL_WEIGHT,
            num_positions=10,
            stop_loss_price=95.0,
        )
        result = calculate_position_size(req)
        # risk = 100 shares * $5 = $500
        assert result.risk_amount == pytest.approx(500.0)

    def test_risk_without_stop_loss(self):
        req = _make_request(
            method=SizingMethod.EQUAL_WEIGHT,
            num_positions=10,
            stop_loss_price=None,
        )
        result = calculate_position_size(req)
        assert result.risk_amount == 0.0


# ---------- Portfolio Constraints ----------


class TestPortfolioConstraints:
    def test_max_single_position(self):
        req = _make_request(risk_pct=0.10, max_position_pct=1.0)
        constraints = PortfolioConstraints(max_single_position_pct=0.05)
        result = calculate_position_size(req, constraints)
        assert result.dollar_amount <= 100_000 * 0.05 + 0.01
        assert result.constrained is True

    def test_max_total_exposure_exceeded(self):
        req = _make_request()
        constraints = PortfolioConstraints(
            current_exposure=100_000.0,
            max_total_exposure_pct=1.0,
        )
        result = calculate_position_size(req, constraints)
        assert result.shares == 0.0
        assert result.constrained is True

    def test_partial_remaining_capacity(self):
        req = _make_request()
        constraints = PortfolioConstraints(
            current_exposure=95_000.0,
            max_total_exposure_pct=1.0,
        )
        result = calculate_position_size(req, constraints)
        # Only 5_000 remaining capacity
        assert result.dollar_amount <= 5_000.0 + 0.01
        assert result.constrained is True

    def test_correlated_exposure_exceeded(self):
        req = _make_request()
        constraints = PortfolioConstraints(
            current_correlated_exposure=40_000.0,
            max_correlated_exposure_pct=0.40,
        )
        result = calculate_position_size(req, constraints)
        assert result.shares == 0.0
        assert result.constrained is True

    def test_no_constraints_unconstrained(self):
        req = _make_request(risk_pct=0.01)
        constraints = PortfolioConstraints()
        result = calculate_position_size(req, constraints)
        assert result.constrained is False

    def test_zero_max_position_pct_returns_zero(self):
        req = _make_request(max_position_pct=0.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0


# ---------- Edge Cases ----------


class TestEdgeCases:
    def test_zero_entry_price(self):
        req = _make_request(entry_price=0.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_negative_equity(self):
        req = _make_request(current_equity=-1000.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_zero_signal_strength(self):
        req = _make_request(signal_strength=0.0)
        result = calculate_position_size(req)
        assert result.shares == 0.0

    def test_very_small_equity(self):
        req = _make_request(current_equity=1.0)
        result = calculate_position_size(req)
        # Should still compute without error
        assert result.shares >= 0.0

    def test_result_fields_present(self):
        req = _make_request()
        result = calculate_position_size(req)
        assert result.strategy_id == "strat-1"
        assert result.signal_strength == 1.0
        assert isinstance(result.constrained, bool)
