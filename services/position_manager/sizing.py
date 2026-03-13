"""Position sizing calculations: fixed-fraction and Kelly Criterion."""

import math

from services.position_manager.models import (
    PositionSizing,
    RiskParams,
    SizingMethod,
)


def fixed_fraction_size(
    price: float,
    risk_params: RiskParams,
    stop_loss_pct: float | None = None,
) -> PositionSizing:
    """Calculate position size using fixed-fraction risk model.

    Risks a fixed percentage of capital. The position size is determined
    by how much capital we are willing to lose if the stop-loss is hit.

    Args:
        price: Current asset price.
        risk_params: Risk parameters (capital, risk_pct, etc.).
        stop_loss_pct: Stop-loss distance as a fraction of price.
            Falls back to risk_params.default_stop_loss_pct.
    """
    if price <= 0:
        return PositionSizing(
            method=SizingMethod.FIXED_FRACTION,
            quantity=0.0,
            risk_amount=0.0,
            position_value=0.0,
        )

    sl_pct = stop_loss_pct if stop_loss_pct is not None else risk_params.default_stop_loss_pct
    risk_amount = risk_params.capital * risk_params.risk_pct
    max_position_value = risk_params.capital * risk_params.max_position_pct

    # quantity = risk_amount / (price * stop_loss_pct)
    if sl_pct <= 0:
        quantity = 0.0
    else:
        quantity = risk_amount / (price * sl_pct)

    position_value = quantity * price
    if position_value > max_position_value:
        quantity = max_position_value / price
        position_value = max_position_value

    return PositionSizing(
        method=SizingMethod.FIXED_FRACTION,
        quantity=quantity,
        risk_amount=min(risk_amount, position_value * sl_pct),
        position_value=quantity * price,
    )


def kelly_criterion_size(
    price: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    risk_params: RiskParams,
    kelly_fraction: float = 0.25,
) -> PositionSizing:
    """Calculate position size using the Kelly Criterion.

    f* = (b*p - q) / b  where b = avg_win/avg_loss, p = win_rate, q = 1-p.
    We apply a fractional Kelly (default 25%) for safety.

    Args:
        price: Current asset price.
        win_rate: Historical win rate [0, 1].
        avg_win: Average winning trade return (absolute value).
        avg_loss: Average losing trade return (absolute value).
        risk_params: Risk parameters.
        kelly_fraction: Fraction of full Kelly to use (0-1).
    """
    if price <= 0 or avg_loss <= 0 or not (0 < win_rate < 1):
        return PositionSizing(
            method=SizingMethod.KELLY,
            quantity=0.0,
            risk_amount=0.0,
            position_value=0.0,
        )

    b = avg_win / avg_loss
    p = win_rate
    q = 1.0 - win_rate

    full_kelly = (b * p - q) / b
    # Clamp to [0, 1] before applying fraction
    full_kelly = max(0.0, min(full_kelly, 1.0))
    fraction = full_kelly * kelly_fraction

    position_value = risk_params.capital * fraction
    max_position_value = risk_params.capital * risk_params.max_position_pct
    if position_value > max_position_value:
        position_value = max_position_value

    quantity = position_value / price if price > 0 else 0.0
    risk_amount = position_value * risk_params.default_stop_loss_pct

    return PositionSizing(
        method=SizingMethod.KELLY,
        quantity=quantity,
        risk_amount=risk_amount,
        position_value=quantity * price,
    )
