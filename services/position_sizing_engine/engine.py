"""
Position Sizing Engine — core sizing logic.

Calculates optimal position sizes using multiple methods:
- Fixed Fractional: risk a fixed % of equity per trade
- Kelly Criterion: mathematically optimal sizing based on win rate and payoff
- Volatility-Adjusted (ATR-based): scale size inversely with volatility
- Equal Weight: divide equity equally across positions
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class SizingMethod(str, Enum):
    FIXED_FRACTIONAL = "fixed_fractional"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    EQUAL_WEIGHT = "equal_weight"


SIZING_METHOD_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    SizingMethod.FIXED_FRACTIONAL: {
        "name": "Fixed Fractional",
        "description": (
            "Risks a fixed percentage of equity per trade. "
            "Position size = (equity * risk_pct) / (entry_price - stop_loss_price)."
        ),
    },
    SizingMethod.KELLY_CRITERION: {
        "name": "Kelly Criterion",
        "description": (
            "Mathematically optimal sizing based on win rate and payoff ratio. "
            "Uses half-Kelly by default for safety. "
            "f = (win_rate * payoff_ratio - (1 - win_rate)) / payoff_ratio."
        ),
    },
    SizingMethod.VOLATILITY_ADJUSTED: {
        "name": "Volatility-Adjusted (ATR)",
        "description": (
            "Scales position size inversely with volatility measured by ATR. "
            "Position size = (equity * risk_pct) / (atr_multiplier * atr)."
        ),
    },
    SizingMethod.EQUAL_WEIGHT: {
        "name": "Equal Weight",
        "description": (
            "Divides available equity equally across a target number of positions. "
            "Position size = equity / num_positions."
        ),
    },
}


@dataclass
class SizingRequest:
    """Input parameters for position sizing."""

    strategy_id: str
    signal_strength: float  # 0.0 to 1.0
    entry_price: float
    stop_loss_price: Optional[float]
    current_equity: float
    max_position_pct: float  # max % of equity in one position (0.0 to 1.0)
    method: SizingMethod = SizingMethod.FIXED_FRACTIONAL
    # Optional parameters for specific methods
    risk_pct: float = 0.02  # risk % of equity per trade
    win_rate: Optional[float] = None  # for Kelly
    payoff_ratio: Optional[float] = None  # avg_win / avg_loss for Kelly
    atr: Optional[float] = None  # for volatility-adjusted
    atr_multiplier: float = 2.0  # for volatility-adjusted
    num_positions: int = 10  # for equal weight
    kelly_fraction: float = 0.5  # fraction of full Kelly to use


@dataclass
class SizingResult:
    """Output of position sizing calculation."""

    shares: float
    dollar_amount: float
    risk_amount: float
    risk_pct: float
    method: str
    strategy_id: str
    signal_strength: float
    constrained: bool  # True if portfolio constraints reduced the size


@dataclass
class PortfolioConstraints:
    """Portfolio-level limits."""

    max_total_exposure_pct: float = 1.0  # max total portfolio exposure (1.0 = 100%)
    max_single_position_pct: float = 0.20  # max single position as % of equity
    max_correlated_exposure_pct: float = 0.40  # max exposure to correlated assets
    current_exposure: float = 0.0  # current total exposure in dollars
    current_correlated_exposure: float = 0.0  # current correlated exposure in dollars


def _calculate_fixed_fractional(req: SizingRequest) -> SizingResult:
    """Risk a fixed percentage of equity per trade."""
    if req.stop_loss_price is None or req.entry_price <= 0:
        return _zero_result(req, SizingMethod.FIXED_FRACTIONAL)

    risk_per_share = abs(req.entry_price - req.stop_loss_price)
    if risk_per_share <= 0:
        return _zero_result(req, SizingMethod.FIXED_FRACTIONAL)

    risk_amount = req.current_equity * req.risk_pct
    shares = risk_amount / risk_per_share
    dollar_amount = shares * req.entry_price

    return SizingResult(
        shares=shares,
        dollar_amount=dollar_amount,
        risk_amount=risk_amount,
        risk_pct=req.risk_pct,
        method=SizingMethod.FIXED_FRACTIONAL,
        strategy_id=req.strategy_id,
        signal_strength=req.signal_strength,
        constrained=False,
    )


def _calculate_kelly(req: SizingRequest) -> SizingResult:
    """Kelly Criterion sizing."""
    win_rate = req.win_rate if req.win_rate is not None else 0.5
    payoff_ratio = req.payoff_ratio if req.payoff_ratio is not None else 1.0

    if payoff_ratio <= 0 or win_rate <= 0 or win_rate >= 1:
        return _zero_result(req, SizingMethod.KELLY_CRITERION)

    # Kelly formula: f = (W * R - (1 - W)) / R
    kelly_f = (win_rate * payoff_ratio - (1 - win_rate)) / payoff_ratio
    kelly_f = max(kelly_f, 0.0)

    # Apply fractional Kelly for safety
    kelly_f *= req.kelly_fraction

    dollar_amount = req.current_equity * kelly_f
    shares = dollar_amount / req.entry_price if req.entry_price > 0 else 0.0

    # Calculate risk based on stop loss if available
    if req.stop_loss_price is not None and req.entry_price > 0:
        risk_per_share = abs(req.entry_price - req.stop_loss_price)
        risk_amount = shares * risk_per_share
    else:
        risk_amount = dollar_amount * kelly_f  # approximate risk

    risk_pct = risk_amount / req.current_equity if req.current_equity > 0 else 0.0

    return SizingResult(
        shares=shares,
        dollar_amount=dollar_amount,
        risk_amount=risk_amount,
        risk_pct=risk_pct,
        method=SizingMethod.KELLY_CRITERION,
        strategy_id=req.strategy_id,
        signal_strength=req.signal_strength,
        constrained=False,
    )


def _calculate_volatility_adjusted(req: SizingRequest) -> SizingResult:
    """ATR-based volatility-adjusted sizing."""
    if req.atr is None or req.atr <= 0 or req.entry_price <= 0:
        return _zero_result(req, SizingMethod.VOLATILITY_ADJUSTED)

    risk_amount = req.current_equity * req.risk_pct
    risk_per_share = req.atr_multiplier * req.atr
    shares = risk_amount / risk_per_share
    dollar_amount = shares * req.entry_price

    return SizingResult(
        shares=shares,
        dollar_amount=dollar_amount,
        risk_amount=risk_amount,
        risk_pct=req.risk_pct,
        method=SizingMethod.VOLATILITY_ADJUSTED,
        strategy_id=req.strategy_id,
        signal_strength=req.signal_strength,
        constrained=False,
    )


def _calculate_equal_weight(req: SizingRequest) -> SizingResult:
    """Equal weight across target number of positions."""
    if req.num_positions <= 0 or req.entry_price <= 0:
        return _zero_result(req, SizingMethod.EQUAL_WEIGHT)

    dollar_amount = req.current_equity / req.num_positions
    shares = dollar_amount / req.entry_price

    # Risk estimate based on stop loss if available
    if req.stop_loss_price is not None:
        risk_per_share = abs(req.entry_price - req.stop_loss_price)
        risk_amount = shares * risk_per_share
    else:
        risk_amount = 0.0

    risk_pct = risk_amount / req.current_equity if req.current_equity > 0 else 0.0

    return SizingResult(
        shares=shares,
        dollar_amount=dollar_amount,
        risk_amount=risk_amount,
        risk_pct=risk_pct,
        method=SizingMethod.EQUAL_WEIGHT,
        strategy_id=req.strategy_id,
        signal_strength=req.signal_strength,
        constrained=False,
    )


def _zero_result(req: SizingRequest, method: SizingMethod) -> SizingResult:
    return SizingResult(
        shares=0.0,
        dollar_amount=0.0,
        risk_amount=0.0,
        risk_pct=0.0,
        method=method,
        strategy_id=req.strategy_id,
        signal_strength=req.signal_strength,
        constrained=False,
    )


_SIZING_FUNCTIONS = {
    SizingMethod.FIXED_FRACTIONAL: _calculate_fixed_fractional,
    SizingMethod.KELLY_CRITERION: _calculate_kelly,
    SizingMethod.VOLATILITY_ADJUSTED: _calculate_volatility_adjusted,
    SizingMethod.EQUAL_WEIGHT: _calculate_equal_weight,
}


def apply_portfolio_constraints(
    result: SizingResult,
    equity: float,
    constraints: PortfolioConstraints,
) -> SizingResult:
    """Apply portfolio-level constraints to a sizing result."""
    if equity <= 0 or result.shares <= 0:
        return result

    constrained = False
    dollar_amount = result.dollar_amount
    entry_price = dollar_amount / result.shares  # recover entry price

    # Constraint 1: max single position size
    max_single = equity * constraints.max_single_position_pct
    if dollar_amount > max_single:
        dollar_amount = max_single
        constrained = True

    # Constraint 2: max total exposure
    max_total = equity * constraints.max_total_exposure_pct
    remaining_capacity = max_total - constraints.current_exposure
    if remaining_capacity <= 0:
        return SizingResult(
            shares=0.0,
            dollar_amount=0.0,
            risk_amount=0.0,
            risk_pct=0.0,
            method=result.method,
            strategy_id=result.strategy_id,
            signal_strength=result.signal_strength,
            constrained=True,
        )
    if dollar_amount > remaining_capacity:
        dollar_amount = remaining_capacity
        constrained = True

    # Constraint 3: max correlated exposure
    corr_remaining = (
        equity * constraints.max_correlated_exposure_pct
        - constraints.current_correlated_exposure
    )
    if corr_remaining <= 0:
        return SizingResult(
            shares=0.0,
            dollar_amount=0.0,
            risk_amount=0.0,
            risk_pct=0.0,
            method=result.method,
            strategy_id=result.strategy_id,
            signal_strength=result.signal_strength,
            constrained=True,
        )
    if dollar_amount > corr_remaining:
        dollar_amount = corr_remaining
        constrained = True

    # Recompute shares and risk
    shares = dollar_amount / entry_price if entry_price > 0 else 0.0
    scale = shares / result.shares if result.shares > 0 else 0.0
    risk_amount = result.risk_amount * scale
    risk_pct = risk_amount / equity if equity > 0 else 0.0

    return SizingResult(
        shares=shares,
        dollar_amount=dollar_amount,
        risk_amount=risk_amount,
        risk_pct=risk_pct,
        method=result.method,
        strategy_id=result.strategy_id,
        signal_strength=result.signal_strength,
        constrained=constrained,
    )


def calculate_position_size(
    req: SizingRequest,
    constraints: Optional[PortfolioConstraints] = None,
) -> SizingResult:
    """Calculate position size for a trade setup.

    Applies the requested sizing method, then enforces portfolio constraints.
    Signal strength is used to scale the final position (0 = no position, 1 = full).
    """
    if req.current_equity <= 0 or req.entry_price <= 0:
        return _zero_result(req, req.method)

    # Apply max_position_pct from the request
    if req.max_position_pct <= 0:
        return _zero_result(req, req.method)

    sizing_fn = _SIZING_FUNCTIONS[req.method]
    result = sizing_fn(req)

    # Scale by signal strength
    if req.signal_strength < 1.0 and result.shares > 0:
        scale = max(req.signal_strength, 0.0)
        result = SizingResult(
            shares=result.shares * scale,
            dollar_amount=result.dollar_amount * scale,
            risk_amount=result.risk_amount * scale,
            risk_pct=result.risk_pct * scale,
            method=result.method,
            strategy_id=result.strategy_id,
            signal_strength=result.signal_strength,
            constrained=result.constrained,
        )

    # Enforce per-request max position cap
    max_dollar = req.current_equity * req.max_position_pct
    if result.dollar_amount > max_dollar and result.shares > 0:
        entry_price = result.dollar_amount / result.shares
        scale = max_dollar / result.dollar_amount
        result = SizingResult(
            shares=result.shares * scale,
            dollar_amount=max_dollar,
            risk_amount=result.risk_amount * scale,
            risk_pct=result.risk_pct * scale,
            method=result.method,
            strategy_id=result.strategy_id,
            signal_strength=result.signal_strength,
            constrained=True,
        )

    # Apply portfolio-level constraints
    if constraints is not None:
        result = apply_portfolio_constraints(result, req.current_equity, constraints)

    return result
