"""Virtual portfolio that tracks positions, balances, and P&L."""

from datetime import datetime
from typing import Dict, List, Optional

from services.paper_trading.models import (
    Fill,
    OrderSide,
    PerformanceSnapshot,
    Position,
    TradeRecord,
)


class VirtualPortfolio:
    """In-memory portfolio tracking positions, cash, and performance.

    Args:
        initial_balance: Starting virtual cash balance.
    """

    def __init__(self, initial_balance: float = 100_000.0):
        self.initial_balance = initial_balance
        self.cash: float = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trade_log: List[TradeRecord] = []
        self._daily_snapshots: List[PerformanceSnapshot] = []
        self._last_snapshot_equity: float = initial_balance

    @property
    def available_balance(self) -> float:
        """Cash available for new orders."""
        return self.cash

    def get_position(self, symbol: str) -> Optional[Position]:
        pos = self.positions.get(symbol)
        if pos and pos.is_flat():
            return None
        return pos

    def apply_fill(self, fill: Fill) -> TradeRecord:
        """Update portfolio state from a fill.

        Returns the resulting TradeRecord.
        """
        pos = self.positions.get(fill.symbol)
        realized_pnl = 0.0

        if pos is None:
            pos = Position(symbol=fill.symbol)
            self.positions[fill.symbol] = pos

        if fill.side == OrderSide.BUY:
            cost = fill.quantity * fill.fill_price + fill.commission
            # Weighted average cost basis
            total_qty = pos.quantity + fill.quantity
            if total_qty > 0:
                pos.avg_cost_basis = (
                    pos.avg_cost_basis * pos.quantity
                    + fill.fill_price * fill.quantity
                ) / total_qty
            pos.quantity = total_qty
            self.cash -= cost
        else:  # SELL
            if pos.quantity > 0:
                realized_pnl = (fill.fill_price - pos.avg_cost_basis) * fill.quantity
                pos.realized_pnl += realized_pnl
            pos.quantity -= fill.quantity
            proceeds = fill.quantity * fill.fill_price - fill.commission
            self.cash += proceeds

        # Clean up flat positions
        if pos.is_flat():
            del self.positions[fill.symbol]

        record = TradeRecord(
            order_id=fill.order_id,
            symbol=fill.symbol,
            side=fill.side,
            quantity=fill.quantity,
            fill_price=fill.fill_price,
            realized_pnl=realized_pnl,
            timestamp=fill.filled_at,
        )
        self.trade_log.append(record)
        return record

    def unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Compute total unrealized P&L across all positions."""
        total = 0.0
        for symbol, pos in self.positions.items():
            price = current_prices.get(symbol)
            if price is not None and pos.quantity > 0:
                total += (price - pos.avg_cost_basis) * pos.quantity
        return total

    def unrealized_pnl_for(self, symbol: str, current_price: float) -> float:
        """Compute unrealized P&L for a single position."""
        pos = self.positions.get(symbol)
        if pos is None or pos.quantity <= 0:
            return 0.0
        return (current_price - pos.avg_cost_basis) * pos.quantity

    def total_realized_pnl(self) -> float:
        """Sum of all realized P&L across positions and closed trades."""
        return sum(t.realized_pnl for t in self.trade_log)

    def total_equity(self, current_prices: Dict[str, float]) -> float:
        """Total portfolio value: cash + market value of positions."""
        market_value = 0.0
        for symbol, pos in self.positions.items():
            price = current_prices.get(symbol, pos.avg_cost_basis)
            market_value += pos.quantity * price
        return self.cash + market_value

    def cumulative_return(self, current_prices: Dict[str, float]) -> float:
        """Cumulative return as a fraction (e.g. 0.05 = 5%)."""
        equity = self.total_equity(current_prices)
        if self.initial_balance == 0:
            return 0.0
        return (equity - self.initial_balance) / self.initial_balance

    def max_position_size(
        self, price: float, max_pct_of_equity: float = 0.1
    ) -> float:
        """Compute maximum position size based on account balance.

        Args:
            price: Current price per unit.
            max_pct_of_equity: Maximum fraction of cash to allocate (default 10%).

        Returns:
            Maximum quantity that can be purchased.
        """
        if price <= 0:
            return 0.0
        allocatable = self.cash * max_pct_of_equity
        return allocatable / price

    def record_daily_snapshot(
        self, date: str, current_prices: Dict[str, float]
    ) -> PerformanceSnapshot:
        """Record end-of-day performance snapshot."""
        equity = self.total_equity(current_prices)
        daily_pnl = equity - self._last_snapshot_equity
        cum_return = self.cumulative_return(current_prices)

        snapshot = PerformanceSnapshot(
            date=date,
            starting_equity=self._last_snapshot_equity,
            ending_equity=equity,
            daily_pnl=daily_pnl,
            cumulative_return=cum_return,
            open_positions=len(self.positions),
            total_trades=len(self.trade_log),
        )
        self._daily_snapshots.append(snapshot)
        self._last_snapshot_equity = equity
        return snapshot

    @property
    def daily_snapshots(self) -> List[PerformanceSnapshot]:
        return list(self._daily_snapshots)

    def get_all_positions(self) -> List[Position]:
        return [p for p in self.positions.values() if not p.is_flat()]

    def summary(self, current_prices: Dict[str, float]) -> dict:
        """Return a summary dict of portfolio state."""
        return {
            "cash": round(self.cash, 2),
            "total_equity": round(self.total_equity(current_prices), 2),
            "unrealized_pnl": round(self.unrealized_pnl(current_prices), 2),
            "realized_pnl": round(self.total_realized_pnl(), 2),
            "cumulative_return_pct": round(
                self.cumulative_return(current_prices) * 100, 4
            ),
            "open_positions": len(self.positions),
            "total_trades": len(self.trade_log),
        }
