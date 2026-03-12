"""Tests for risk management module."""

import math

import pytest

from services.risk_management.risk_management import (
    RiskCheckResult,
    RiskConfig,
    StopLossLevel,
    StopLossType,
    PositionSizeResult,
    calculate_position_size,
    calculate_stop_loss,
    check_portfolio_risk,
    load_config,
    _calculate_current_drawdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_config(**overrides) -> RiskConfig:
    return RiskConfig(**overrides)


# ---------------------------------------------------------------------------
# StopLoss tests
# ---------------------------------------------------------------------------


class TestCalculateStopLossATR:
    def test_long_atr_stop(self):
        config = _default_config(stop_loss_type=StopLossType.ATR, atr_multiplier=2.0)
        result = calculate_stop_loss(100.0, "LONG", config, atr=5.0)
        assert result.stop_price == 90.0  # 100 - 2*5
        assert result.stop_type == StopLossType.ATR
        assert result.risk_per_unit == 10.0
        assert result.risk_pct == pytest.approx(0.1)

    def test_short_atr_stop(self):
        config = _default_config(stop_loss_type=StopLossType.ATR, atr_multiplier=1.5)
        result = calculate_stop_loss(100.0, "SHORT", config, atr=4.0)
        assert result.stop_price == 106.0  # 100 + 1.5*4
        assert result.risk_per_unit == 6.0

    def test_atr_missing_raises(self):
        config = _default_config(stop_loss_type=StopLossType.ATR)
        with pytest.raises(ValueError, match="atr"):
            calculate_stop_loss(100.0, "LONG", config, atr=None)

    def test_atr_negative_raises(self):
        config = _default_config(stop_loss_type=StopLossType.ATR)
        with pytest.raises(ValueError, match="atr"):
            calculate_stop_loss(100.0, "LONG", config, atr=-1.0)

    def test_zero_atr(self):
        config = _default_config(stop_loss_type=StopLossType.ATR, atr_multiplier=2.0)
        result = calculate_stop_loss(100.0, "LONG", config, atr=0.0)
        assert result.stop_price == 100.0
        assert result.risk_per_unit == 0.0

    def test_large_atr_stop_clamped_to_zero(self):
        config = _default_config(stop_loss_type=StopLossType.ATR, atr_multiplier=10.0)
        result = calculate_stop_loss(50.0, "LONG", config, atr=10.0)
        # 50 - 100 = -50, clamped to 0
        assert result.stop_price == 0.0


class TestCalculateStopLossPercentage:
    def test_long_percentage_stop(self):
        config = _default_config(
            stop_loss_type=StopLossType.PERCENTAGE, stop_loss_pct=0.05
        )
        result = calculate_stop_loss(200.0, "LONG", config)
        assert result.stop_price == 190.0  # 200 - 200*0.05
        assert result.risk_pct == pytest.approx(0.05)

    def test_short_percentage_stop(self):
        config = _default_config(
            stop_loss_type=StopLossType.PERCENTAGE, stop_loss_pct=0.03
        )
        result = calculate_stop_loss(200.0, "SHORT", config)
        assert result.stop_price == 206.0  # 200 + 200*0.03


class TestCalculateStopLossTrailing:
    def test_long_trailing_from_entry(self):
        config = _default_config(
            stop_loss_type=StopLossType.TRAILING, trailing_stop_pct=0.05
        )
        result = calculate_stop_loss(100.0, "LONG", config)
        assert result.stop_price == 95.0  # 100 - 100*0.05

    def test_long_trailing_from_highest(self):
        config = _default_config(
            stop_loss_type=StopLossType.TRAILING, trailing_stop_pct=0.05
        )
        result = calculate_stop_loss(100.0, "LONG", config, highest_price=120.0)
        assert result.stop_price == 114.0  # 120 - 120*0.05

    def test_short_trailing_from_entry(self):
        config = _default_config(
            stop_loss_type=StopLossType.TRAILING, trailing_stop_pct=0.04
        )
        result = calculate_stop_loss(100.0, "SHORT", config)
        # For short, stop above: 100 + 100*0.04 = 104
        assert result.stop_price == 104.0

    def test_short_trailing_from_highest(self):
        config = _default_config(
            stop_loss_type=StopLossType.TRAILING, trailing_stop_pct=0.04
        )
        result = calculate_stop_loss(100.0, "SHORT", config, highest_price=90.0)
        # 90 + 90*0.04 = 93.6
        assert result.stop_price == pytest.approx(93.6)


class TestStopLossEdgeCases:
    def test_invalid_side(self):
        config = _default_config(stop_loss_type=StopLossType.PERCENTAGE)
        with pytest.raises(ValueError, match="side"):
            calculate_stop_loss(100.0, "INVALID", config)

    def test_zero_entry_price(self):
        config = _default_config(stop_loss_type=StopLossType.PERCENTAGE)
        with pytest.raises(ValueError, match="entry_price"):
            calculate_stop_loss(0.0, "LONG", config)

    def test_negative_entry_price(self):
        config = _default_config(stop_loss_type=StopLossType.PERCENTAGE)
        with pytest.raises(ValueError, match="entry_price"):
            calculate_stop_loss(-10.0, "LONG", config)


# ---------------------------------------------------------------------------
# Position sizing tests
# ---------------------------------------------------------------------------


class TestCalculatePositionSize:
    def test_basic_sizing(self):
        config = _default_config(
            max_position_pct=0.05, max_open_positions=10, max_portfolio_heat=0.20
        )
        stop = StopLossLevel(
            stop_price=95.0,
            stop_type=StopLossType.PERCENTAGE,
            risk_per_unit=5.0,
            risk_pct=0.05,
        )
        result = calculate_position_size(100000.0, 100.0, stop, config)
        assert result.max_shares > 0
        assert result.position_value <= 100000.0 * 0.05
        assert result.risk_amount > 0

    def test_risk_budget_limits_size(self):
        config = _default_config(
            max_position_pct=1.0,  # Very generous position limit
            max_open_positions=10,
            max_portfolio_heat=0.02,  # Very tight risk budget
        )
        stop = StopLossLevel(
            stop_price=90.0,
            stop_type=StopLossType.ATR,
            risk_per_unit=10.0,
            risk_pct=0.1,
        )
        result = calculate_position_size(100000.0, 100.0, stop, config)
        assert result.limited_by == "risk_budget"
        # risk budget = 100000 * 0.02 / 10 = 200
        # size = 200 / 10 = 20 shares
        assert result.max_shares == pytest.approx(20.0)

    def test_position_pct_limits_size(self):
        config = _default_config(
            max_position_pct=0.01,  # Very tight position limit
            max_open_positions=10,
            max_portfolio_heat=1.0,  # Very generous risk budget
        )
        stop = StopLossLevel(
            stop_price=99.0,
            stop_type=StopLossType.PERCENTAGE,
            risk_per_unit=1.0,
            risk_pct=0.01,
        )
        result = calculate_position_size(100000.0, 100.0, stop, config)
        assert result.limited_by == "max_position_pct"
        assert result.max_shares == pytest.approx(10.0)  # 1000 / 100

    def test_max_value_limits_size(self):
        config = _default_config(
            max_position_pct=1.0,
            max_position_value=500.0,  # $500 cap
            max_open_positions=10,
            max_portfolio_heat=1.0,
        )
        stop = StopLossLevel(
            stop_price=99.0,
            stop_type=StopLossType.PERCENTAGE,
            risk_per_unit=1.0,
            risk_pct=0.01,
        )
        result = calculate_position_size(100000.0, 100.0, stop, config)
        assert result.limited_by == "max_position_value"
        assert result.max_shares == pytest.approx(5.0)

    def test_zero_equity(self):
        config = _default_config()
        stop = StopLossLevel(
            stop_price=95.0,
            stop_type=StopLossType.PERCENTAGE,
            risk_per_unit=5.0,
            risk_pct=0.05,
        )
        result = calculate_position_size(0.0, 100.0, stop, config)
        assert result.max_shares == 0.0
        assert result.limited_by == "invalid_inputs"

    def test_zero_entry_price(self):
        config = _default_config()
        stop = StopLossLevel(
            stop_price=0.0,
            stop_type=StopLossType.PERCENTAGE,
            risk_per_unit=0.0,
            risk_pct=0.0,
        )
        result = calculate_position_size(100000.0, 0.0, stop, config)
        assert result.max_shares == 0.0

    def test_zero_risk_per_unit(self):
        """When stop is at entry (zero risk), sizing uses position limits only."""
        config = _default_config(max_position_pct=0.10)
        stop = StopLossLevel(
            stop_price=100.0,
            stop_type=StopLossType.ATR,
            risk_per_unit=0.0,
            risk_pct=0.0,
        )
        result = calculate_position_size(100000.0, 100.0, stop, config)
        assert result.max_shares == pytest.approx(100.0)  # 10000 / 100
        assert result.risk_amount == 0.0


# ---------------------------------------------------------------------------
# Portfolio risk check tests
# ---------------------------------------------------------------------------


class TestCheckPortfolioRisk:
    def test_clean_trade_allowed(self):
        config = _default_config()
        result = check_portfolio_risk(
            proposed_symbol="BTC-USD",
            proposed_value=1000.0,
            proposed_risk=50.0,
            portfolio_equity=100000.0,
            current_positions=[],
            config=config,
        )
        assert result.allowed is True
        assert result.violations == []

    def test_max_positions_exceeded(self):
        config = _default_config(max_open_positions=2)
        positions = [
            {"symbol": "BTC-USD", "value": 1000, "risk": 50},
            {"symbol": "ETH-USD", "value": 1000, "risk": 50},
        ]
        result = check_portfolio_risk(
            "SOL-USD", 1000, 50, 100000, positions, config
        )
        assert result.allowed is False
        assert any("Max open positions" in v for v in result.violations)

    def test_portfolio_heat_exceeded(self):
        config = _default_config(max_portfolio_heat=0.05)
        positions = [
            {"symbol": "BTC-USD", "value": 5000, "risk": 4000},
        ]
        result = check_portfolio_risk(
            "ETH-USD", 2000, 2000, 100000, positions, config
        )
        assert result.allowed is False
        assert any("heat" in v.lower() for v in result.violations)

    def test_portfolio_heat_warning(self):
        config = _default_config(max_portfolio_heat=0.10)
        # Current risk = 7000, proposed = 1500 -> total = 8500 -> 8.5% (>80% of 10%)
        positions = [
            {"symbol": "BTC-USD", "value": 10000, "risk": 7000},
        ]
        result = check_portfolio_risk(
            "ETH-USD", 2000, 1500, 100000, positions, config
        )
        assert result.allowed is True
        assert any("approaching" in w.lower() for w in result.warnings)

    def test_drawdown_halt(self):
        config = _default_config(max_drawdown_threshold=0.05)
        positions = [
            {"symbol": "BTC-USD", "value": 5000, "risk": 100, "unrealized_pnl": -6000},
        ]
        result = check_portfolio_risk(
            "ETH-USD", 1000, 50, 100000, positions, config
        )
        assert result.allowed is False
        assert any("drawdown" in v.lower() for v in result.violations)

    def test_sector_exposure_exceeded(self):
        config = _default_config(max_sector_exposure_pct=0.30)
        sector_map = {"BTC-USD": "Crypto", "ETH-USD": "Crypto", "SOL-USD": "Crypto"}
        positions = [
            {"symbol": "BTC-USD", "value": 20000, "risk": 500},
            {"symbol": "ETH-USD", "value": 10000, "risk": 300},
        ]
        result = check_portfolio_risk(
            "SOL-USD", 5000, 100, 100000, positions, config,
            sector_map=sector_map,
        )
        assert result.allowed is False
        assert any("Sector" in v and "Crypto" in v for v in result.violations)

    def test_sector_exposure_warning(self):
        config = _default_config(max_sector_exposure_pct=0.40)
        sector_map = {"BTC-USD": "Crypto", "ETH-USD": "Crypto"}
        positions = [
            {"symbol": "BTC-USD", "value": 30000, "risk": 500},
        ]
        # 30000 + 3000 = 33000 / 100000 = 33% (>80% of 40%)
        result = check_portfolio_risk(
            "ETH-USD", 3000, 100, 100000, positions, config,
            sector_map=sector_map,
        )
        assert result.allowed is True
        assert any("Crypto" in w for w in result.warnings)

    def test_correlation_exposure_exceeded(self):
        config = _default_config(
            max_correlated_exposure_pct=0.25, correlation_threshold=0.70
        )
        corr_matrix = {("BTC-USD", "ETH-USD"): 0.85}
        positions = [
            {"symbol": "BTC-USD", "value": 20000, "risk": 500},
        ]
        # Correlated value = 10000 (proposed) + 20000 (BTC) = 30000 -> 30%
        result = check_portfolio_risk(
            "ETH-USD", 10000, 200, 100000, positions, config,
            correlation_matrix=corr_matrix,
        )
        assert result.allowed is False
        assert any("Correlated" in v for v in result.violations)

    def test_correlation_below_threshold_ignored(self):
        config = _default_config(
            max_correlated_exposure_pct=0.25, correlation_threshold=0.70
        )
        corr_matrix = {("BTC-USD", "SOL-USD"): 0.50}  # Below threshold
        positions = [
            {"symbol": "BTC-USD", "value": 20000, "risk": 500},
        ]
        result = check_portfolio_risk(
            "SOL-USD", 10000, 200, 100000, positions, config,
            correlation_matrix=corr_matrix,
        )
        assert result.allowed is True

    def test_correlation_reverse_pair_lookup(self):
        """Correlation matrix may have (A,B) but query asks for (B,A)."""
        config = _default_config(
            max_correlated_exposure_pct=0.25, correlation_threshold=0.70
        )
        # Only (ETH, BTC) stored, but we query for BTC proposing ETH
        corr_matrix = {("ETH-USD", "BTC-USD"): 0.90}
        positions = [
            {"symbol": "BTC-USD", "value": 20000, "risk": 500},
        ]
        result = check_portfolio_risk(
            "ETH-USD", 10000, 200, 100000, positions, config,
            correlation_matrix=corr_matrix,
        )
        assert result.allowed is False

    def test_zero_equity(self):
        config = _default_config()
        result = check_portfolio_risk("BTC-USD", 1000, 50, 0, [], config)
        assert result.allowed is False

    def test_multiple_violations(self):
        config = _default_config(
            max_open_positions=1,
            max_portfolio_heat=0.01,
        )
        positions = [
            {"symbol": "BTC-USD", "value": 5000, "risk": 900},
        ]
        result = check_portfolio_risk(
            "ETH-USD", 5000, 200, 100000, positions, config
        )
        assert result.allowed is False
        assert len(result.violations) >= 2


# ---------------------------------------------------------------------------
# Drawdown helper
# ---------------------------------------------------------------------------


class TestCalculateCurrentDrawdown:
    def test_no_positions(self):
        assert _calculate_current_drawdown([], 100000) == 0.0

    def test_positive_pnl(self):
        positions = [{"unrealized_pnl": 500}]
        assert _calculate_current_drawdown(positions, 100000) == 0.0

    def test_negative_pnl(self):
        positions = [{"unrealized_pnl": -5000}]
        assert _calculate_current_drawdown(positions, 100000) == pytest.approx(0.05)

    def test_zero_equity(self):
        assert _calculate_current_drawdown([{"unrealized_pnl": -100}], 0) == 0.0


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_full_config(self):
        raw = {
            "position_limits": {
                "max_position_pct": 0.10,
                "max_position_value": 25000,
            },
            "stop_loss": {
                "type": "trailing",
                "atr_multiplier": 3.0,
                "percentage": 0.04,
                "trailing_pct": 0.06,
            },
            "portfolio_limits": {
                "max_portfolio_heat": 0.15,
                "max_drawdown_threshold": 0.08,
                "max_open_positions": 5,
                "max_sector_exposure_pct": 0.35,
                "max_correlated_exposure_pct": 0.25,
            },
            "correlation": {
                "threshold": 0.80,
            },
        }
        config = load_config(raw)
        assert config.max_position_pct == 0.10
        assert config.max_position_value == 25000
        assert config.stop_loss_type == StopLossType.TRAILING
        assert config.atr_multiplier == 3.0
        assert config.stop_loss_pct == 0.04
        assert config.trailing_stop_pct == 0.06
        assert config.max_portfolio_heat == 0.15
        assert config.max_drawdown_threshold == 0.08
        assert config.max_open_positions == 5
        assert config.max_sector_exposure_pct == 0.35
        assert config.max_correlated_exposure_pct == 0.25
        assert config.correlation_threshold == 0.80

    def test_empty_config_uses_defaults(self):
        config = load_config({})
        assert config.max_position_pct == 0.05
        assert config.stop_loss_type == StopLossType.ATR
        assert config.max_portfolio_heat == 0.20
        assert config.max_open_positions == 10

    def test_partial_config(self):
        raw = {"stop_loss": {"type": "percentage"}}
        config = load_config(raw)
        assert config.stop_loss_type == StopLossType.PERCENTAGE
        assert config.max_position_pct == 0.05  # default preserved

    def test_unknown_stop_type_defaults_to_atr(self):
        raw = {"stop_loss": {"type": "unknown_type"}}
        config = load_config(raw)
        assert config.stop_loss_type == StopLossType.ATR
