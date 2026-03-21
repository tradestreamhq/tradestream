"""
PnL calculation engine with FIFO, LIFO, and average cost basis methods.

Tracks lot-level positions and computes realized/unrealized P&L.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class CostBasisMethod(str, Enum):
    FIFO = "fifo"
    LIFO = "lifo"
    AVERAGE = "average"


@dataclass
class Lot:
    entry_price: Decimal
    size: Decimal
    timestamp: datetime
    lot_id: Optional[str] = None

    @property
    def cost(self) -> Decimal:
        return self.entry_price * self.size


@dataclass
class RealizedPnL:
    lot_entry_price: Decimal
    exit_price: Decimal
    size: Decimal
    pnl: Decimal
    lot_timestamp: datetime
    exit_timestamp: datetime

    @property
    def pnl_pct(self) -> Decimal:
        if self.lot_entry_price == 0:
            return Decimal(0)
        return (self.exit_price - self.lot_entry_price) / self.lot_entry_price * 100


@dataclass
class UnrealizedPnL:
    lot_entry_price: Decimal
    current_price: Decimal
    size: Decimal
    pnl: Decimal
    lot_timestamp: datetime


@dataclass
class Position:
    symbol: str
    lots: List[Lot] = field(default_factory=list)
    realized: List[RealizedPnL] = field(default_factory=list)

    @property
    def total_size(self) -> Decimal:
        return sum((lot.size for lot in self.lots), Decimal(0))

    @property
    def total_cost(self) -> Decimal:
        return sum((lot.cost for lot in self.lots), Decimal(0))

    @property
    def avg_entry_price(self) -> Decimal:
        total = self.total_size
        if total == 0:
            return Decimal(0)
        return self.total_cost / total

    @property
    def total_realized_pnl(self) -> Decimal:
        return sum((r.pnl for r in self.realized), Decimal(0))

    def unrealized_pnl(self, current_price: Decimal) -> List[UnrealizedPnL]:
        result = []
        for lot in self.lots:
            pnl = (current_price - lot.entry_price) * lot.size
            result.append(
                UnrealizedPnL(
                    lot_entry_price=lot.entry_price,
                    current_price=current_price,
                    size=lot.size,
                    pnl=pnl,
                    lot_timestamp=lot.timestamp,
                )
            )
        return result

    def total_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        return sum((u.pnl for u in self.unrealized_pnl(current_price)), Decimal(0))


class PnLEngine:
    """Manages positions and computes P&L across multiple symbols."""

    def __init__(self, method: CostBasisMethod = CostBasisMethod.FIFO):
        self.method = method
        self.positions: dict[str, Position] = {}

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def add_buy(
        self,
        symbol: str,
        price: Decimal,
        size: Decimal,
        timestamp: datetime,
        lot_id: Optional[str] = None,
    ) -> Lot:
        """Record a buy, creating a new lot."""
        lot = Lot(entry_price=price, size=size, timestamp=timestamp, lot_id=lot_id)
        pos = self.get_position(symbol)
        pos.lots.append(lot)
        return lot

    def add_sell(
        self,
        symbol: str,
        price: Decimal,
        size: Decimal,
        timestamp: datetime,
    ) -> List[RealizedPnL]:
        """Record a sell, matching against lots using the configured method."""
        pos = self.get_position(symbol)
        if size > pos.total_size:
            raise ValueError(
                f"Sell size {size} exceeds position size {pos.total_size} for {symbol}"
            )

        remaining = size
        realized_list: List[RealizedPnL] = []

        if self.method == CostBasisMethod.AVERAGE:
            realized_list = self._sell_average(pos, price, size, timestamp)
        else:
            lots = self._ordered_lots(pos)
            while remaining > 0 and lots:
                lot = lots[0]
                fill = min(remaining, lot.size)
                pnl = (price - lot.entry_price) * fill
                realized_list.append(
                    RealizedPnL(
                        lot_entry_price=lot.entry_price,
                        exit_price=price,
                        size=fill,
                        pnl=pnl,
                        lot_timestamp=lot.timestamp,
                        exit_timestamp=timestamp,
                    )
                )
                lot.size -= fill
                remaining -= fill
                if lot.size == 0:
                    pos.lots.remove(lot)
                    lots.pop(0)

        pos.realized.extend(realized_list)
        return realized_list

    def _ordered_lots(self, pos: Position) -> List[Lot]:
        """Return lots in order based on the cost basis method."""
        if self.method == CostBasisMethod.FIFO:
            return sorted(pos.lots, key=lambda l: l.timestamp)
        elif self.method == CostBasisMethod.LIFO:
            return sorted(pos.lots, key=lambda l: l.timestamp, reverse=True)
        return list(pos.lots)

    def _sell_average(
        self,
        pos: Position,
        price: Decimal,
        size: Decimal,
        timestamp: datetime,
    ) -> List[RealizedPnL]:
        """Handle sell using average cost basis."""
        avg_cost = pos.avg_entry_price
        pnl = (price - avg_cost) * size
        realized = [
            RealizedPnL(
                lot_entry_price=avg_cost,
                exit_price=price,
                size=size,
                pnl=pnl,
                lot_timestamp=pos.lots[0].timestamp if pos.lots else timestamp,
                exit_timestamp=timestamp,
            )
        ]

        # Proportionally reduce all lots
        total = pos.total_size
        ratio = (total - size) / total if total > 0 else Decimal(0)
        for lot in pos.lots:
            lot.size *= ratio

        # Remove empty lots
        pos.lots = [lot for lot in pos.lots if lot.size > 0]

        return realized
