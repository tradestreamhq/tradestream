"""Profit-and-loss calculation utilities."""

from services.position_manager.models import Position, Side


def unrealized_pnl(position: Position, current_price: float) -> float:
    """Calculate unrealized PnL for an open position.

    For LONG: (current_price - entry_price) * quantity
    For SHORT: (entry_price - current_price) * quantity
    """
    if position.side == Side.LONG:
        return (current_price - position.entry_price) * position.quantity
    return (position.entry_price - current_price) * position.quantity


def realized_pnl(position: Position, exit_price: float) -> float:
    """Calculate realized PnL when closing a position.

    For LONG: (exit_price - entry_price) * quantity
    For SHORT: (entry_price - exit_price) * quantity
    """
    if position.side == Side.LONG:
        return (exit_price - position.entry_price) * position.quantity
    return (position.entry_price - exit_price) * position.quantity


def should_stop_loss(position: Position, current_price: float) -> bool:
    """Check whether current price has breached the stop-loss level."""
    if position.stop_loss is None:
        return False
    if position.side == Side.LONG:
        return current_price <= position.stop_loss
    return current_price >= position.stop_loss


def should_take_profit(position: Position, current_price: float) -> bool:
    """Check whether current price has reached the take-profit level."""
    if position.take_profit is None:
        return False
    if position.side == Side.LONG:
        return current_price >= position.take_profit
    return current_price <= position.take_profit
