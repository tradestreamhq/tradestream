"""Disposal method implementations for tax lot accounting."""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from services.tax_lots.models import RealizedGain


def _holding_period(acquisition: datetime, disposal: datetime) -> str:
    delta = disposal - acquisition
    return "LONG_TERM" if delta.days > 365 else "SHORT_TERM"


def _consume_lots(
    ordered_lots: List[Dict],
    quantity: float,
    sale_price: float,
    disposal_date: datetime,
) -> Tuple[List[RealizedGain], List[Dict]]:
    """Consume lots in the given order and return realized gains plus updates.

    Returns:
        Tuple of (list of realized gains, list of dicts with lot_id and new remaining_quantity).
    """
    gains = []
    updates = []
    remaining_to_sell = quantity

    for lot in ordered_lots:
        if remaining_to_sell <= 0:
            break

        available = float(lot["remaining_quantity"])
        if available <= 0:
            continue

        disposed = min(available, remaining_to_sell)
        remaining_to_sell -= disposed
        new_remaining = available - disposed

        updates.append({"lot_id": lot["lot_id"], "remaining_quantity": new_remaining})

        acq_date = lot["acquisition_date"]
        if not isinstance(acq_date, datetime):
            acq_date = datetime.fromisoformat(str(acq_date))

        gain = RealizedGain(
            lot_id=lot["lot_id"],
            symbol=lot["symbol"],
            quantity_disposed=disposed,
            cost_basis=float(lot["cost_basis"]),
            sale_price=sale_price,
            realized_gain=round((sale_price - float(lot["cost_basis"])) * disposed, 8),
            acquisition_date=acq_date,
            disposal_date=disposal_date,
            holding_period=_holding_period(acq_date, disposal_date),
        )
        gains.append(gain)

    if remaining_to_sell > 1e-9:
        raise ValueError(
            f"Insufficient lots: {remaining_to_sell:.8f} units could not be disposed"
        )

    return gains, updates


def dispose_fifo(
    lots: List[Dict], quantity: float, sale_price: float, disposal_date: datetime
) -> Tuple[List[RealizedGain], List[Dict]]:
    """Dispose lots using First-In-First-Out ordering."""
    ordered = sorted(lots, key=lambda l: l["acquisition_date"])
    return _consume_lots(ordered, quantity, sale_price, disposal_date)


def dispose_lifo(
    lots: List[Dict], quantity: float, sale_price: float, disposal_date: datetime
) -> Tuple[List[RealizedGain], List[Dict]]:
    """Dispose lots using Last-In-First-Out ordering."""
    ordered = sorted(lots, key=lambda l: l["acquisition_date"], reverse=True)
    return _consume_lots(ordered, quantity, sale_price, disposal_date)


def dispose_specific(
    lots: List[Dict],
    lot_id: str,
    quantity: float,
    sale_price: float,
    disposal_date: datetime,
) -> Tuple[List[RealizedGain], List[Dict]]:
    """Dispose a specific identified lot."""
    target = [l for l in lots if l["lot_id"] == lot_id]
    if not target:
        raise ValueError(f"Lot '{lot_id}' not found")
    return _consume_lots(target, quantity, sale_price, disposal_date)
