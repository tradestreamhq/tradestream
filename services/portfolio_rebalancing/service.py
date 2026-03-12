"""Portfolio rebalancing service.

Connects to the database to read current positions and prices,
computes rebalancing trades, and optionally executes them via
the paper trading system.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import asyncpg
from absl import flags, logging

from services.portfolio_rebalancing.rebalancer import (
    AllocationTarget,
    CurrentHolding,
    RebalanceConstraints,
    RebalanceReport,
    RebalanceTrade,
    TradeSide,
    compute_rebalance_trades,
    format_rebalance_report,
)

FLAGS = flags.FLAGS


class RebalancingService:
    """Manages portfolio rebalancing against target allocations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def get_current_holdings(self) -> List[CurrentHolding]:
        """Fetch current holdings from the paper portfolio."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl
            FROM paper_portfolio
            WHERE quantity != 0
            ORDER BY symbol
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        holdings = []
        for row in rows:
            qty = float(row["quantity"])
            price = float(row["avg_entry_price"])
            holdings.append(CurrentHolding(
                symbol=row["symbol"],
                quantity=qty,
                current_price=price,
                market_value=qty * price,
            ))
        return holdings

    async def get_available_cash(self, initial_capital: float = 10000.0) -> float:
        """Calculate available cash from initial capital minus invested + realized P&L."""
        positions_query = """
            SELECT COALESCE(SUM(quantity * avg_entry_price), 0) as total_invested
            FROM paper_portfolio
            WHERE quantity != 0
        """
        realized_query = """
            SELECT COALESCE(SUM(pnl), 0) as total_realized
            FROM paper_trades
            WHERE status = 'CLOSED'
        """
        async with self.db_pool.acquire() as conn:
            invested_row = await conn.fetchrow(positions_query)
            realized_row = await conn.fetchrow(realized_query)

        total_invested = float(invested_row["total_invested"])
        total_realized = float(realized_row["total_realized"])
        return initial_capital + total_realized - total_invested

    async def get_target_allocation(self) -> List[AllocationTarget]:
        """Load target allocation from the database.

        Falls back to equal-weight allocation across current holdings
        if no explicit targets are stored.
        """
        # Check for explicit allocation targets table
        check_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'rebalance_targets'
            )
        """
        async with self.db_pool.acquire() as conn:
            table_exists = await conn.fetchval(check_query)

            if table_exists:
                rows = await conn.fetch(
                    "SELECT symbol, target_pct FROM rebalance_targets WHERE is_active = TRUE"
                )
                if rows:
                    return [
                        AllocationTarget(
                            symbol=row["symbol"],
                            target_pct=float(row["target_pct"]),
                        )
                        for row in rows
                    ]

        # Fallback: equal-weight across current holdings
        holdings = await self.get_current_holdings()
        if not holdings:
            return []

        equal_weight = 1.0 / len(holdings)
        return [
            AllocationTarget(symbol=h.symbol, target_pct=equal_weight)
            for h in holdings
        ]

    async def run_rebalance(
        self,
        targets: Optional[List[AllocationTarget]] = None,
        current_prices: Optional[Dict[str, float]] = None,
        constraints: Optional[RebalanceConstraints] = None,
        dry_run: bool = True,
    ) -> RebalanceReport:
        """Execute a full rebalancing cycle.

        Args:
            targets: Override target allocation. If None, loads from DB.
            current_prices: Override prices. If None, uses entry prices.
            constraints: Override constraints.
            dry_run: If True, compute but don't execute trades.

        Returns:
            RebalanceReport with computed (and optionally executed) trades.
        """
        if targets is None:
            targets = await self.get_target_allocation()

        holdings = await self.get_current_holdings()
        cash = await self.get_available_cash()

        # Use provided prices or fall back to entry prices from holdings
        if current_prices is None:
            current_prices = {h.symbol: h.current_price for h in holdings}

        # Update holdings with live prices
        for h in holdings:
            if h.symbol in current_prices:
                h.current_price = current_prices[h.symbol]
                h.market_value = h.quantity * h.current_price

        # Ensure all target symbols have prices
        for t in targets:
            if t.symbol not in current_prices:
                logging.warning(
                    "No price for target symbol %s, skipping", t.symbol
                )

        report = compute_rebalance_trades(
            targets=targets,
            holdings=holdings,
            cash=cash,
            current_prices=current_prices,
            constraints=constraints,
        )

        logging.info(
            "Rebalance computed: %d trades, %d skipped",
            len(report.trades),
            len(report.skipped),
        )

        if not dry_run and report.trades:
            await self._execute_trades(report.trades)

        return report

    async def _execute_trades(self, trades: List[RebalanceTrade]) -> None:
        """Execute rebalance trades by inserting into paper_trades and updating paper_portfolio."""
        async with self.db_pool.acquire() as conn:
            for trade in trades:
                side = trade.side.value
                logging.info(
                    "Executing rebalance trade: %s %s %.8f @ %.2f",
                    side,
                    trade.symbol,
                    trade.quantity,
                    trade.estimated_price,
                )

                # Insert into paper_trades
                await conn.execute(
                    """
                    INSERT INTO paper_trades (symbol, side, entry_price, quantity, status)
                    VALUES ($1, $2, $3, $4, 'OPEN')
                    """,
                    trade.symbol,
                    side,
                    trade.estimated_price,
                    trade.quantity,
                )

                # Update paper_portfolio
                if trade.side == TradeSide.BUY:
                    await conn.execute(
                        """
                        INSERT INTO paper_portfolio (symbol, quantity, avg_entry_price)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (symbol) DO UPDATE SET
                            quantity = paper_portfolio.quantity + EXCLUDED.quantity,
                            avg_entry_price = (
                                paper_portfolio.avg_entry_price * paper_portfolio.quantity
                                + EXCLUDED.avg_entry_price * EXCLUDED.quantity
                            ) / (paper_portfolio.quantity + EXCLUDED.quantity),
                            updated_at = NOW()
                        """,
                        trade.symbol,
                        trade.quantity,
                        trade.estimated_price,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE paper_portfolio
                        SET quantity = quantity - $2,
                            updated_at = NOW()
                        WHERE symbol = $1
                        """,
                        trade.symbol,
                        trade.quantity,
                    )

        logging.info("Executed %d rebalance trades", len(trades))
