"""Portfolio snapshot capture logic."""

import logging
from datetime import date
from typing import Optional

import asyncpg

from services.portfolio_snapshot.models import PortfolioSnapshot, SnapshotPosition

logger = logging.getLogger(__name__)


async def capture_snapshot(pool: asyncpg.Pool) -> PortfolioSnapshot:
    """Capture current portfolio state as a snapshot for today.

    Reads positions from paper_portfolio and computes equity from
    paper_trades realized P&L plus unrealized P&L.
    """
    today = date.today()

    async with pool.acquire() as conn:
        # Compute equity: realized P&L + unrealized P&L
        realized_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(pnl), 0) AS total_realized "
            "FROM paper_trades WHERE status = 'CLOSED'"
        )
        unrealized_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(unrealized_pnl), 0) AS total_unrealized "
            "FROM paper_portfolio"
        )

        total_realized = float(realized_row["total_realized"])
        total_unrealized = float(unrealized_row["total_unrealized"])
        total_equity = total_realized + total_unrealized

        # Gather positions
        position_rows = await conn.fetch(
            "SELECT symbol, quantity, quantity * avg_entry_price + unrealized_pnl "
            "AS market_value FROM paper_portfolio WHERE quantity != 0 ORDER BY symbol"
        )

        positions = [
            SnapshotPosition(
                symbol=row["symbol"],
                quantity=float(row["quantity"]),
                market_value=float(row["market_value"]),
            )
            for row in position_rows
        ]

        # Look up previous snapshot for daily change calculation
        prev = await conn.fetchrow(
            "SELECT total_equity FROM portfolio_snapshots "
            "WHERE snapshot_date < $1 ORDER BY snapshot_date DESC LIMIT 1",
            today,
        )

        daily_change: Optional[float] = None
        daily_change_pct: Optional[float] = None
        if prev is not None:
            prev_equity = float(prev["total_equity"])
            daily_change = total_equity - prev_equity
            if prev_equity != 0:
                daily_change_pct = round(daily_change / prev_equity * 100, 4)

        # Upsert snapshot row
        snapshot_row = await conn.fetchrow(
            "INSERT INTO portfolio_snapshots "
            "(snapshot_date, total_equity, cash_balance, margin_used, "
            "daily_change, daily_change_pct) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (snapshot_date) DO UPDATE SET "
            "total_equity = EXCLUDED.total_equity, "
            "cash_balance = EXCLUDED.cash_balance, "
            "margin_used = EXCLUDED.margin_used, "
            "daily_change = EXCLUDED.daily_change, "
            "daily_change_pct = EXCLUDED.daily_change_pct "
            "RETURNING id",
            today,
            total_equity,
            0.0,  # cash_balance - placeholder
            0.0,  # margin_used - placeholder
            daily_change,
            daily_change_pct,
        )

        snapshot_id = str(snapshot_row["id"])

        # Replace position records for this snapshot
        await conn.execute(
            "DELETE FROM portfolio_snapshot_positions WHERE snapshot_id = $1",
            snapshot_row["id"],
        )
        for pos in positions:
            await conn.execute(
                "INSERT INTO portfolio_snapshot_positions "
                "(snapshot_id, symbol, quantity, market_value) "
                "VALUES ($1, $2, $3, $4)",
                snapshot_row["id"],
                pos.symbol,
                pos.quantity,
                pos.market_value,
            )

    snapshot = PortfolioSnapshot(
        id=snapshot_id,
        snapshot_date=today,
        total_equity=total_equity,
        cash_balance=0.0,
        margin_used=0.0,
        positions=positions,
        daily_change=daily_change,
        daily_change_pct=daily_change_pct,
    )

    logger.info("Captured portfolio snapshot for %s: equity=%.2f", today, total_equity)
    return snapshot
