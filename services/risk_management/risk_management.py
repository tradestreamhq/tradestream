"""Risk management module with position sizing, stop-loss, and portfolio limits.

Provides configurable rules that enforce position limits, calculate stop-loss
levels based on volatility, and prevent overexposure to correlated assets.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StopLossType(str, Enum):
    ATR = "atr"
    PERCENTAGE = "percentage"
    TRAILING = "trailing"


@dataclass
class RiskConfig:
    """Configuration for risk management rules."""

    # Position-level limits
    max_position_pct: float = 0.05  # Max 5% of portfolio per position
    max_position_value: float = float("inf")  # Absolute dollar cap

    # Stop-loss settings
    stop_loss_type: StopLossType = StopLossType.ATR
    atr_multiplier: float = 2.0  # Stop at 2x ATR below entry
    stop_loss_pct: float = 0.02  # 2% stop for percentage-based
    trailing_stop_pct: float = 0.03  # 3% trailing stop

    # Portfolio-level limits
    max_portfolio_heat: float = 0.20  # Max 20% of capital at risk
    max_drawdown_threshold: float = 0.10  # 10% max drawdown before halt
    max_open_positions: int = 10
    max_sector_exposure_pct: float = 0.40  # Max 40% in one sector
    max_correlated_exposure_pct: float = 0.30  # Max 30% in correlated assets

    # Correlation settings
    correlation_threshold: float = 0.70  # Assets above this are "correlated"


@dataclass
class StopLossLevel:
    """Calculated stop-loss price and metadata."""

    stop_price: float
    stop_type: StopLossType
    risk_per_unit: float  # Distance from entry to stop
    risk_pct: float  # Risk as percentage of entry price


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""

    max_shares: float
    position_value: float
    risk_amount: float  # Dollar amount at risk
    risk_pct_of_portfolio: float
    limited_by: str  # Which constraint was binding


@dataclass
class RiskCheckResult:
    """Result of a portfolio-level risk check."""

    allowed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stop-loss calculations
# ---------------------------------------------------------------------------


def calculate_stop_loss(
    entry_price: float,
    side: str,
    config: RiskConfig,
    atr: Optional[float] = None,
    highest_price: Optional[float] = None,
) -> StopLossLevel:
    """Calculate the stop-loss level for a position.

    Args:
        entry_price: The entry price of the position.
        side: "LONG" or "SHORT".
        config: Risk configuration.
        atr: Average True Range value (required for ATR-based stops).
        highest_price: Highest price since entry (for trailing stops).

    Returns:
        StopLossLevel with computed stop price and risk metrics.
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")

    stop_type = config.stop_loss_type

    if stop_type == StopLossType.ATR:
        if atr is None or atr < 0:
            raise ValueError("atr must be a non-negative number for ATR-based stops")
        distance = atr * config.atr_multiplier
    elif stop_type == StopLossType.PERCENTAGE:
        distance = entry_price * config.stop_loss_pct
    elif stop_type == StopLossType.TRAILING:
        ref_price = highest_price if highest_price is not None else entry_price
        distance = ref_price * config.trailing_stop_pct
    else:
        raise ValueError(f"Unknown stop loss type: {stop_type}")

    if side == "LONG":
        stop_price = (
            (highest_price if highest_price is not None else entry_price) - distance
            if stop_type == StopLossType.TRAILING
            else entry_price - distance
        )
    elif side == "SHORT":
        stop_price = (
            entry_price + distance
            if stop_type != StopLossType.TRAILING
            else (
                (highest_price if highest_price is not None else entry_price) + distance
            )
        )
    else:
        raise ValueError(f"side must be 'LONG' or 'SHORT', got '{side}'")

    stop_price = max(stop_price, 0.0)
    risk_per_unit = abs(entry_price - stop_price)
    risk_pct = risk_per_unit / entry_price if entry_price > 0 else 0.0

    return StopLossLevel(
        stop_price=round(stop_price, 8),
        stop_type=stop_type,
        risk_per_unit=round(risk_per_unit, 8),
        risk_pct=round(risk_pct, 6),
    )


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------


def calculate_position_size(
    portfolio_equity: float,
    entry_price: float,
    stop_loss: StopLossLevel,
    config: RiskConfig,
) -> PositionSizeResult:
    """Determine maximum position size given risk constraints.

    Uses the risk-per-trade approach: size = risk_budget / risk_per_unit,
    then caps by max_position_pct and max_position_value.

    Args:
        portfolio_equity: Total portfolio equity.
        entry_price: Planned entry price.
        stop_loss: Pre-calculated stop-loss level.
        config: Risk configuration.

    Returns:
        PositionSizeResult with the constrained position size.
    """
    if portfolio_equity <= 0 or entry_price <= 0:
        return PositionSizeResult(
            max_shares=0.0,
            position_value=0.0,
            risk_amount=0.0,
            risk_pct_of_portfolio=0.0,
            limited_by="invalid_inputs",
        )

    # Budget: how much dollar risk we can afford per trade
    # Use max_position_pct * portfolio as the max position value
    max_value_by_pct = portfolio_equity * config.max_position_pct
    max_value = min(max_value_by_pct, config.max_position_value)
    size_by_value = max_value / entry_price
    limited_by = "max_position_pct"
    if config.max_position_value < max_value_by_pct:
        limited_by = "max_position_value"

    # Risk-based sizing: risk_budget / risk_per_unit
    if stop_loss.risk_per_unit > 0:
        # The per-trade risk budget is the portfolio heat budget spread evenly
        risk_budget = (
            portfolio_equity
            * config.max_portfolio_heat
            / max(config.max_open_positions, 1)
        )
        size_by_risk = risk_budget / stop_loss.risk_per_unit
        if size_by_risk < size_by_value:
            size_by_value = size_by_risk
            limited_by = "risk_budget"

    max_shares = max(size_by_value, 0.0)
    position_value = max_shares * entry_price
    risk_amount = max_shares * stop_loss.risk_per_unit
    risk_pct = risk_amount / portfolio_equity if portfolio_equity > 0 else 0.0

    return PositionSizeResult(
        max_shares=round(max_shares, 8),
        position_value=round(position_value, 2),
        risk_amount=round(risk_amount, 2),
        risk_pct_of_portfolio=round(risk_pct, 6),
        limited_by=limited_by,
    )


# ---------------------------------------------------------------------------
# Portfolio-level risk checks
# ---------------------------------------------------------------------------


def check_portfolio_risk(
    proposed_symbol: str,
    proposed_value: float,
    proposed_risk: float,
    portfolio_equity: float,
    current_positions: List[Dict[str, Any]],
    config: RiskConfig,
    correlation_matrix: Optional[Dict[Tuple[str, str], float]] = None,
    sector_map: Optional[Dict[str, str]] = None,
) -> RiskCheckResult:
    """Check whether a proposed trade violates portfolio-level risk limits.

    Args:
        proposed_symbol: Symbol of the proposed trade.
        proposed_value: Dollar value of the proposed position.
        proposed_risk: Dollar risk of the proposed position.
        portfolio_equity: Total portfolio equity.
        current_positions: List of dicts with keys: symbol, value, risk, sector.
        config: Risk configuration.
        correlation_matrix: Optional dict mapping (sym_a, sym_b) -> correlation.
        sector_map: Optional dict mapping symbol -> sector name.

    Returns:
        RiskCheckResult with allowed flag and any violations/warnings.
    """
    violations = []
    warnings = []

    if portfolio_equity <= 0:
        return RiskCheckResult(
            allowed=False, violations=["Portfolio equity is zero or negative"]
        )

    # 1. Max open positions
    num_positions = len(current_positions)
    if num_positions >= config.max_open_positions:
        violations.append(
            f"Max open positions reached: {num_positions}/{config.max_open_positions}"
        )

    # 2. Portfolio heat check
    current_risk = sum(p.get("risk", 0.0) for p in current_positions)
    new_total_risk = current_risk + proposed_risk
    heat_pct = new_total_risk / portfolio_equity
    if heat_pct > config.max_portfolio_heat:
        violations.append(
            f"Portfolio heat would be {heat_pct:.1%}, "
            f"exceeds limit of {config.max_portfolio_heat:.1%}"
        )
    elif heat_pct > config.max_portfolio_heat * 0.8:
        warnings.append(
            f"Portfolio heat at {heat_pct:.1%}, "
            f"approaching limit of {config.max_portfolio_heat:.1%}"
        )

    # 3. Drawdown check
    current_drawdown = _calculate_current_drawdown(current_positions, portfolio_equity)
    if current_drawdown >= config.max_drawdown_threshold:
        violations.append(
            f"Current drawdown {current_drawdown:.1%} exceeds "
            f"threshold of {config.max_drawdown_threshold:.1%}. Trading halted."
        )

    # 4. Sector exposure
    if sector_map is not None:
        proposed_sector = sector_map.get(proposed_symbol, "Other")
        sector_values: Dict[str, float] = {}
        for p in current_positions:
            sec = p.get("sector", sector_map.get(p["symbol"], "Other"))
            sector_values[sec] = sector_values.get(sec, 0.0) + p.get("value", 0.0)
        sector_values[proposed_sector] = (
            sector_values.get(proposed_sector, 0.0) + proposed_value
        )

        for sec, val in sector_values.items():
            exposure = val / portfolio_equity
            if exposure > config.max_sector_exposure_pct:
                violations.append(
                    f"Sector '{sec}' exposure would be {exposure:.1%}, "
                    f"exceeds limit of {config.max_sector_exposure_pct:.1%}"
                )
            elif exposure > config.max_sector_exposure_pct * 0.8:
                warnings.append(
                    f"Sector '{sec}' exposure at {exposure:.1%}, "
                    f"approaching limit of {config.max_sector_exposure_pct:.1%}"
                )

    # 5. Correlation-based exposure
    if correlation_matrix is not None:
        correlated_value = proposed_value
        for p in current_positions:
            sym = p["symbol"]
            pair = (
                (proposed_symbol, sym)
                if (proposed_symbol, sym) in correlation_matrix
                else (sym, proposed_symbol)
            )
            corr = correlation_matrix.get(pair, 0.0)
            if abs(corr) >= config.correlation_threshold:
                correlated_value += p.get("value", 0.0)

        correlated_exposure = correlated_value / portfolio_equity
        if correlated_exposure > config.max_correlated_exposure_pct:
            violations.append(
                f"Correlated exposure would be {correlated_exposure:.1%}, "
                f"exceeds limit of {config.max_correlated_exposure_pct:.1%}"
            )
        elif correlated_exposure > config.max_correlated_exposure_pct * 0.8:
            warnings.append(
                f"Correlated exposure at {correlated_exposure:.1%}, "
                f"approaching limit of {config.max_correlated_exposure_pct:.1%}"
            )

    return RiskCheckResult(
        allowed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )


def _calculate_current_drawdown(
    positions: List[Dict[str, Any]], portfolio_equity: float
) -> float:
    """Estimate current drawdown from unrealized losses."""
    if portfolio_equity <= 0:
        return 0.0
    total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in positions)
    if total_unrealized >= 0:
        return 0.0
    return abs(total_unrealized) / portfolio_equity


# ---------------------------------------------------------------------------
# Config loading from YAML
# ---------------------------------------------------------------------------


def load_config(config_dict: Dict[str, Any]) -> RiskConfig:
    """Load a RiskConfig from a parsed YAML dictionary.

    Expected YAML structure:
        position_limits:
            max_position_pct: 0.05
            max_position_value: 50000
        stop_loss:
            type: atr
            atr_multiplier: 2.0
            percentage: 0.02
            trailing_pct: 0.03
        portfolio_limits:
            max_portfolio_heat: 0.20
            max_drawdown_threshold: 0.10
            max_open_positions: 10
            max_sector_exposure_pct: 0.40
            max_correlated_exposure_pct: 0.30
        correlation:
            threshold: 0.70
    """
    pos = config_dict.get("position_limits", {})
    sl = config_dict.get("stop_loss", {})
    port = config_dict.get("portfolio_limits", {})
    corr = config_dict.get("correlation", {})

    stop_type_str = sl.get("type", "atr").lower()
    try:
        stop_type = StopLossType(stop_type_str)
    except ValueError:
        stop_type = StopLossType.ATR

    return RiskConfig(
        max_position_pct=float(pos.get("max_position_pct", 0.05)),
        max_position_value=float(pos.get("max_position_value", float("inf"))),
        stop_loss_type=stop_type,
        atr_multiplier=float(sl.get("atr_multiplier", 2.0)),
        stop_loss_pct=float(sl.get("percentage", 0.02)),
        trailing_stop_pct=float(sl.get("trailing_pct", 0.03)),
        max_portfolio_heat=float(port.get("max_portfolio_heat", 0.20)),
        max_drawdown_threshold=float(port.get("max_drawdown_threshold", 0.10)),
        max_open_positions=int(port.get("max_open_positions", 10)),
        max_sector_exposure_pct=float(port.get("max_sector_exposure_pct", 0.40)),
        max_correlated_exposure_pct=float(
            port.get("max_correlated_exposure_pct", 0.30)
        ),
        correlation_threshold=float(corr.get("threshold", 0.70)),
    )
