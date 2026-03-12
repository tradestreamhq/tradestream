"""Core position reconciliation logic."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import asyncpg

from services.reconciliation.exchange_client import ExchangePositionClient
from services.reconciliation.models import (
    Discrepancy,
    DiscrepancyType,
    PositionSnapshot,
    ReconciliationReport,
)

logger = logging.getLogger(__name__)

# Default threshold for auto-reconciliation (absolute quantity difference)
DEFAULT_AUTO_RECONCILE_THRESHOLD = 0.0


async def get_internal_positions(db_pool: asyncpg.Pool) -> List[PositionSnapshot]:
    """Fetch all non-zero positions from the internal paper_portfolio table."""
    query = """
        SELECT symbol, quantity, avg_entry_price
        FROM paper_portfolio
        WHERE quantity != 0
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [
        PositionSnapshot(
            symbol=row["symbol"],
            quantity=float(row["quantity"]),
            avg_entry_price=float(row["avg_entry_price"]),
        )
        for row in rows
    ]


async def auto_reconcile_position(
    db_pool: asyncpg.Pool,
    symbol: str,
    exchange_quantity: float,
) -> None:
    """Update internal position to match exchange quantity."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE paper_portfolio SET quantity = $1, updated_at = NOW()
            WHERE symbol = $2
            """,
            exchange_quantity,
            symbol,
        )
    logger.info("Auto-reconciled %s to quantity %s", symbol, exchange_quantity)


def reconcile(
    internal: List[PositionSnapshot],
    exchange: List[PositionSnapshot],
    auto_reconcile_threshold: float = DEFAULT_AUTO_RECONCILE_THRESHOLD,
) -> ReconciliationReport:
    """Compare internal positions against exchange positions and produce a report.

    Args:
        internal: Positions from internal tracking.
        exchange: Positions from exchange API.
        auto_reconcile_threshold: Max absolute difference to auto-reconcile.
            0.0 disables auto-reconciliation.

    Returns:
        A ReconciliationReport with any discrepancies found.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    internal_map: Dict[str, PositionSnapshot] = {p.symbol: p for p in internal}
    exchange_map: Dict[str, PositionSnapshot] = {p.symbol: p for p in exchange}

    all_symbols = set(internal_map.keys()) | set(exchange_map.keys())
    discrepancies: List[Discrepancy] = []

    for symbol in sorted(all_symbols):
        int_pos = internal_map.get(symbol)
        ext_pos = exchange_map.get(symbol)

        if int_pos and not ext_pos:
            # Phantom position: tracked internally but not on exchange
            discrepancies.append(
                Discrepancy(
                    symbol=symbol,
                    type=DiscrepancyType.PHANTOM_POSITION,
                    internal_quantity=int_pos.quantity,
                    exchange_quantity=None,
                    difference=int_pos.quantity,
                )
            )
        elif ext_pos and not int_pos:
            # Missing internal: on exchange but not tracked
            discrepancies.append(
                Discrepancy(
                    symbol=symbol,
                    type=DiscrepancyType.MISSING_INTERNAL,
                    internal_quantity=None,
                    exchange_quantity=ext_pos.quantity,
                    difference=ext_pos.quantity,
                )
            )
        elif int_pos and ext_pos:
            diff = int_pos.quantity - ext_pos.quantity
            if abs(diff) > 1e-12:  # Floating point tolerance
                should_auto = (
                    auto_reconcile_threshold > 0
                    and abs(diff) <= auto_reconcile_threshold
                )
                discrepancies.append(
                    Discrepancy(
                        symbol=symbol,
                        type=DiscrepancyType.QUANTITY_MISMATCH,
                        internal_quantity=int_pos.quantity,
                        exchange_quantity=ext_pos.quantity,
                        difference=diff,
                        auto_reconciled=should_auto,
                    )
                )

    auto_reconciled_count = sum(1 for d in discrepancies if d.auto_reconciled)
    status = "MATCHED" if not discrepancies else "DISCREPANCIES_FOUND"

    return ReconciliationReport(
        run_id=run_id,
        timestamp=timestamp,
        status=status,
        total_positions_checked=len(all_symbols),
        discrepancies=discrepancies,
        auto_reconciled_count=auto_reconciled_count,
    )
