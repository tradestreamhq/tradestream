"""Position management models and lifecycle tracking.

Tracks individual positions from entry to exit with real-time mark-to-market
P&L calculation, position grouping by strategy and asset class, and a
closed-position archive.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class ManagedPosition:
    """A tracked position with full lifecycle state."""

    id: str
    symbol: str
    side: PositionSide
    quantity: float
    filled_quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    status: PositionStatus
    strategy_name: Optional[str]
    asset_class: str
    opened_at: str
    updated_at: str
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    signal_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PositionSummary:
    """Aggregated position stats for a group (strategy or asset class)."""

    group_key: str
    num_open: int
    num_closed: int
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_exposure: float


def calculate_unrealized_pnl(
    side: PositionSide,
    quantity: float,
    entry_price: float,
    current_price: float,
) -> float:
    """Calculate mark-to-market unrealized P&L."""
    if side == PositionSide.LONG:
        return round(quantity * (current_price - entry_price), 8)
    else:
        return round(quantity * (entry_price - current_price), 8)


def calculate_realized_pnl(
    side: PositionSide,
    quantity: float,
    entry_price: float,
    exit_price: float,
) -> float:
    """Calculate realized P&L for a closed (or partially closed) quantity."""
    if side == PositionSide.LONG:
        return round(quantity * (exit_price - entry_price), 8)
    else:
        return round(quantity * (entry_price - exit_price), 8)


def determine_status(
    filled_quantity: float,
    quantity: float,
    closed_quantity: float,
) -> PositionStatus:
    """Determine position lifecycle status from fill/close quantities."""
    if closed_quantity >= quantity and quantity > 0:
        return PositionStatus.CLOSED
    if closed_quantity > 0:
        return PositionStatus.PARTIALLY_CLOSED
    if filled_quantity >= quantity and quantity > 0:
        return PositionStatus.FILLED
    if filled_quantity > 0:
        return PositionStatus.PARTIAL_FILL
    return PositionStatus.OPEN


def mark_to_market(
    position: ManagedPosition,
    current_price: float,
) -> ManagedPosition:
    """Update a position with the latest market price."""
    pnl = calculate_unrealized_pnl(
        position.side,
        position.filled_quantity,
        position.entry_price,
        current_price,
    )
    now = datetime.now(timezone.utc).isoformat()
    return ManagedPosition(
        id=position.id,
        symbol=position.symbol,
        side=position.side,
        quantity=position.quantity,
        filled_quantity=position.filled_quantity,
        entry_price=position.entry_price,
        current_price=current_price,
        unrealized_pnl=pnl,
        realized_pnl=position.realized_pnl,
        status=position.status,
        strategy_name=position.strategy_name,
        asset_class=position.asset_class,
        opened_at=position.opened_at,
        updated_at=now,
        closed_at=position.closed_at,
        exit_price=position.exit_price,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        signal_id=position.signal_id,
        tags=position.tags,
    )


def close_position(
    position: ManagedPosition,
    exit_price: float,
    close_quantity: Optional[float] = None,
) -> ManagedPosition:
    """Close (fully or partially) a position at the given exit price.

    Returns a new ManagedPosition with updated realized P&L and status.
    """
    qty = close_quantity if close_quantity is not None else position.filled_quantity
    qty = min(qty, position.filled_quantity)

    realized = calculate_realized_pnl(
        position.side, qty, position.entry_price, exit_price
    )

    remaining = position.filled_quantity - qty
    closed_qty = position.quantity - remaining
    new_status = determine_status(position.quantity, position.quantity, closed_qty)

    now = datetime.now(timezone.utc).isoformat()

    return ManagedPosition(
        id=position.id,
        symbol=position.symbol,
        side=position.side,
        quantity=position.quantity,
        filled_quantity=remaining,
        entry_price=position.entry_price,
        current_price=exit_price,
        unrealized_pnl=(
            calculate_unrealized_pnl(
                position.side, remaining, position.entry_price, exit_price
            )
            if remaining > 0
            else 0.0
        ),
        realized_pnl=round(position.realized_pnl + realized, 8),
        status=new_status,
        strategy_name=position.strategy_name,
        asset_class=position.asset_class,
        opened_at=position.opened_at,
        updated_at=now,
        closed_at=now if new_status == PositionStatus.CLOSED else position.closed_at,
        exit_price=exit_price if new_status == PositionStatus.CLOSED else None,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        signal_id=position.signal_id,
        tags=position.tags,
    )


def classify_asset_class(symbol: str) -> str:
    """Classify a trading symbol into an asset class."""
    crypto_bases = {
        "BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC",
        "LINK", "UNI", "DOGE", "XRP", "BNB", "LTC", "ATOM",
    }
    base = symbol.split("-")[0].split("/")[0].upper()
    if base in crypto_bases:
        return "Crypto"
    return "Other"


def summarize_positions(
    positions: List[ManagedPosition],
    group_by: str = "strategy",
) -> List[PositionSummary]:
    """Group positions and compute aggregate stats.

    Args:
        positions: List of positions to summarize.
        group_by: "strategy" or "asset_class".
    """
    groups: Dict[str, List[ManagedPosition]] = {}
    for p in positions:
        key = p.strategy_name or "unknown" if group_by == "strategy" else p.asset_class
        groups.setdefault(key, []).append(p)

    summaries = []
    for key, group in sorted(groups.items()):
        open_positions = [p for p in group if p.status != PositionStatus.CLOSED]
        closed_positions = [p for p in group if p.status == PositionStatus.CLOSED]
        total_unrealized = sum(p.unrealized_pnl for p in open_positions)
        total_realized = sum(p.realized_pnl for p in group)
        total_exposure = sum(
            p.filled_quantity * p.current_price for p in open_positions
        )

        summaries.append(
            PositionSummary(
                group_key=key,
                num_open=len(open_positions),
                num_closed=len(closed_positions),
                total_unrealized_pnl=round(total_unrealized, 8),
                total_realized_pnl=round(total_realized, 8),
                total_exposure=round(total_exposure, 2),
            )
        )

    return summaries
