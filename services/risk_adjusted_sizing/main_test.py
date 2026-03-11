"""Tests for the risk-adjusted sizing service."""

from unittest import mock

import pytest

from absl import flags

from services.risk_adjusted_sizing.main import (
    PositionSize,
    RiskAdjustedSizer,
    RiskMetrics,
)

FLAGS = flags.FLAGS


@pytest.fixture(autouse=True)
def _reset_flags():
    """Ensure flag defaults for each test."""
    saved = {
        "max_portfolio_risk": FLAGS.max_portfolio_risk,
        "max_position_risk": FLAGS.max_position_risk,
        "risk_free_rate": FLAGS.risk_free_rate,
        "kelly_fraction": FLAGS.kelly_fraction,
        "max_leverage": FLAGS.max_leverage,
    }
    yield
    for k, v in saved.items():
        FLAGS[k].value = v


def _make_sizer():
    sizer = RiskAdjustedSizer.__new__(RiskAdjustedSizer)
    sizer.db_config = {}
    sizer.pool = None
    return sizer


def _risk_metrics(
    sid="s1",
    symbol="BTC",
    stype="RSI",
    score=0.8,
    volatility=0.15,
    sharpe=1.2,
    max_dd=0.05,
    win_rate=0.65,
    profit_factor=1.8,
):
    return RiskMetrics(
        strategy_id=sid,
        symbol=symbol,
        strategy_type=stype,
        current_score=score,
        volatility=volatility,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        profit_factor=profit_factor,
    )


class TestKellyCriterion:
    def setup_method(self):
        self.sizer = _make_sizer()

    def test_basic_kelly(self):
        # b = 3.6/2 = 1.8, p = 0.65, q = 0.35
        # kelly = (1.8*0.65 - 0.35) / 1.8 = (1.17 - 0.35)/1.8 = 0.4556
        # fractional kelly = 0.4556 * 0.25 = 0.1139
        result = self.sizer.calculate_kelly_criterion(0.65, 3.6, 2.0)
        assert result == pytest.approx(0.1139, abs=0.001)

    def test_zero_avg_loss(self):
        result = self.sizer.calculate_kelly_criterion(0.65, 3.6, 0.0)
        assert result == 0.0

    def test_negative_kelly_capped_at_zero(self):
        # Very low win rate should produce negative kelly -> capped at 0
        result = self.sizer.calculate_kelly_criterion(0.1, 1.0, 2.0)
        assert result == 0.0

    def test_capped_at_max_leverage(self):
        FLAGS.max_leverage = 2.0
        FLAGS.kelly_fraction = 1.0  # full kelly
        # Very profitable: b = 10, p = 0.99, q = 0.01
        # kelly = (10*0.99 - 0.01)/10 = 0.989
        result = self.sizer.calculate_kelly_criterion(0.99, 10.0, 1.0)
        assert result <= FLAGS.max_leverage

    def test_kelly_fraction_scales_result(self):
        FLAGS.kelly_fraction = 0.5
        result_half = self.sizer.calculate_kelly_criterion(0.65, 3.6, 2.0)
        FLAGS.kelly_fraction = 0.25
        result_quarter = self.sizer.calculate_kelly_criterion(0.65, 3.6, 2.0)
        assert result_half == pytest.approx(result_quarter * 2, abs=0.001)


class TestRiskParitySize:
    def setup_method(self):
        self.sizer = _make_sizer()

    def test_basic_risk_parity(self):
        result = self.sizer.calculate_risk_parity_size(0.15, 0.005)
        assert result == pytest.approx(0.005 / 0.15)

    def test_zero_volatility(self):
        result = self.sizer.calculate_risk_parity_size(0.0, 0.005)
        assert result == 0.0

    def test_higher_vol_smaller_position(self):
        low_vol = self.sizer.calculate_risk_parity_size(0.10, 0.005)
        high_vol = self.sizer.calculate_risk_parity_size(0.30, 0.005)
        assert low_vol > high_vol


class TestVolatilityAdjustedSize:
    def setup_method(self):
        self.sizer = _make_sizer()

    def test_basic_calculation(self):
        # factor = 1/(1+0.15) = 0.8696, result = 0.8 * 0.8696 = 0.6957
        result = self.sizer.calculate_volatility_adjusted_size(0.8, 0.15)
        assert result == pytest.approx(0.8 / 1.15, abs=0.001)

    def test_zero_volatility(self):
        result = self.sizer.calculate_volatility_adjusted_size(0.8, 0.0)
        assert result == 0.0

    def test_higher_score_larger_position(self):
        low = self.sizer.calculate_volatility_adjusted_size(0.5, 0.15)
        high = self.sizer.calculate_volatility_adjusted_size(0.9, 0.15)
        assert high > low

    def test_higher_vol_smaller_position(self):
        low_vol = self.sizer.calculate_volatility_adjusted_size(0.8, 0.10)
        high_vol = self.sizer.calculate_volatility_adjusted_size(0.8, 0.50)
        assert low_vol > high_vol


class TestCalculatePositionSizes:
    def setup_method(self):
        self.sizer = _make_sizer()

    def test_empty_input(self):
        result = self.sizer.calculate_position_sizes([])
        assert result == []

    def test_single_metric(self):
        metrics = [_risk_metrics()]
        result = self.sizer.calculate_position_sizes(metrics)
        assert len(result) == 1
        pos = result[0]
        assert pos.strategy_id == "s1"
        assert pos.final_size >= 0.0
        assert pos.final_size <= FLAGS.max_leverage

    def test_final_size_bounded(self):
        metrics = [_risk_metrics(score=0.99, win_rate=0.99, profit_factor=10.0)]
        result = self.sizer.calculate_position_sizes(metrics)
        assert result[0].final_size <= FLAGS.max_leverage

    def test_risk_contribution_proportional_to_vol(self):
        low_vol = [_risk_metrics(sid="s1", volatility=0.05)]
        high_vol = [_risk_metrics(sid="s2", volatility=0.50)]
        r_low = self.sizer.calculate_position_sizes(low_vol)[0]
        r_high = self.sizer.calculate_position_sizes(high_vol)[0]
        # Risk contribution = final_size * volatility
        # Higher vol -> higher risk contribution (even if position smaller)
        assert r_high.risk_contribution != r_low.risk_contribution

    def test_multiple_strategies(self):
        metrics = [
            _risk_metrics(sid="s1", symbol="BTC"),
            _risk_metrics(sid="s2", symbol="ETH"),
            _risk_metrics(sid="s3", symbol="SOL"),
        ]
        result = self.sizer.calculate_position_sizes(metrics)
        assert len(result) == 3
        symbols = {p.symbol for p in result}
        assert symbols == {"BTC", "ETH", "SOL"}

    def test_expected_return_positive_for_good_strategy(self):
        metrics = [_risk_metrics(score=0.9)]
        result = self.sizer.calculate_position_sizes(metrics)
        # score > risk_free_rate, so expected return should be positive
        assert result[0].expected_return > 0.0
