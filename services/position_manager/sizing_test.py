"""Tests for position sizing calculations."""

import pytest

from services.position_manager.models import RiskParams, SizingMethod
from services.position_manager.sizing import fixed_fraction_size, kelly_criterion_size


class TestFixedFractionSize:
    def _default_params(self, **overrides):
        defaults = dict(
            capital=100_000,
            risk_pct=0.02,
            max_position_pct=0.1,
            default_stop_loss_pct=0.05,
        )
        defaults.update(overrides)
        return RiskParams(**defaults)

    def test_basic_sizing(self):
        params = self._default_params()
        result = fixed_fraction_size(price=50_000, risk_params=params)
        assert result.method == SizingMethod.FIXED_FRACTION
        # risk = 100k * 0.02 = 2000; qty = 2000 / (50000 * 0.05) = 0.8
        assert result.quantity == pytest.approx(0.8, rel=1e-6)
        assert result.position_value == pytest.approx(40_000, rel=1e-6)

    def test_capped_by_max_position(self):
        # max_position_pct = 0.01 → max value = 1000
        params = self._default_params(max_position_pct=0.01)
        result = fixed_fraction_size(price=100, risk_params=params)
        assert result.position_value <= 100_000 * 0.01 + 1e-9

    def test_zero_price_returns_zero(self):
        params = self._default_params()
        result = fixed_fraction_size(price=0, risk_params=params)
        assert result.quantity == 0.0

    def test_custom_stop_loss_pct(self):
        params = self._default_params()
        result = fixed_fraction_size(price=1000, risk_params=params, stop_loss_pct=0.10)
        # risk = 2000; qty = 2000 / (1000 * 0.10) = 20
        assert result.quantity == pytest.approx(20.0, rel=1e-6)

    def test_small_stop_loss_capped(self):
        params = self._default_params(max_position_pct=0.1)
        # tiny stop → large raw quantity, should be capped
        result = fixed_fraction_size(price=100, risk_params=params, stop_loss_pct=0.001)
        assert result.position_value <= 100_000 * 0.1 + 1e-9


class TestKellyCriterionSize:
    def _default_params(self, **overrides):
        defaults = dict(
            capital=100_000,
            risk_pct=0.02,
            max_position_pct=0.1,
            default_stop_loss_pct=0.05,
        )
        defaults.update(overrides)
        return RiskParams(**defaults)

    def test_positive_edge(self):
        params = self._default_params()
        result = kelly_criterion_size(
            price=50_000,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=0.02,
            risk_params=params,
            kelly_fraction=0.25,
        )
        assert result.method == SizingMethod.KELLY
        assert result.quantity > 0
        assert result.position_value > 0

    def test_no_edge_returns_zero(self):
        params = self._default_params()
        # win_rate = 0.3, avg_win = 0.01, avg_loss = 0.02 → negative Kelly
        result = kelly_criterion_size(
            price=50_000,
            win_rate=0.3,
            avg_win=0.01,
            avg_loss=0.02,
            risk_params=params,
        )
        assert result.quantity == 0.0

    def test_zero_loss_returns_zero(self):
        params = self._default_params()
        result = kelly_criterion_size(
            price=50_000,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=0.0,
            risk_params=params,
        )
        assert result.quantity == 0.0

    def test_capped_by_max_position(self):
        params = self._default_params(max_position_pct=0.01)
        result = kelly_criterion_size(
            price=100,
            win_rate=0.9,
            avg_win=0.10,
            avg_loss=0.01,
            risk_params=params,
            kelly_fraction=1.0,
        )
        assert result.position_value <= 100_000 * 0.01 + 1e-9

    def test_kelly_fraction_scales_down(self):
        params = self._default_params()
        full = kelly_criterion_size(
            price=1000,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=0.02,
            risk_params=params,
            kelly_fraction=1.0,
        )
        quarter = kelly_criterion_size(
            price=1000,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=0.02,
            risk_params=params,
            kelly_fraction=0.25,
        )
        assert quarter.quantity < full.quantity

    def test_invalid_win_rate_returns_zero(self):
        params = self._default_params()
        for wr in (0.0, 1.0, -0.1):
            result = kelly_criterion_size(
                price=1000,
                win_rate=wr,
                avg_win=0.03,
                avg_loss=0.02,
                risk_params=params,
            )
            assert result.quantity == 0.0
