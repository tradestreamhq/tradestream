"""Fee tracking service — records, attributes, and aggregates trading fees."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

from services.fee_tracker.models import FeeRecordCreate, FeeType

logger = logging.getLogger(__name__)


class FeeTracker:
    """Tracks trading fees against strategies and provides analytics."""

    def __init__(self, db_pool: asyncpg.Pool):
        self._pool = db_pool

    async def record_fee(self, fee: FeeRecordCreate) -> Dict[str, Any]:
        """Persist a fee record and return the created row."""
        query = """
            INSERT INTO trading_fees
                (trade_id, strategy_id, fee_type, amount, currency, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id, trade_id, strategy_id, fee_type, amount, currency, created_at
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                fee.trade_id,
                fee.strategy_id,
                fee.fee_type.value,
                fee.amount,
                fee.currency,
            )
        return _row_to_dict(row)

    async def get_fees(
        self,
        strategy_id: Optional[str] = None,
        fee_type: Optional[FeeType] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return fee records with optional filters."""
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if strategy_id:
            conditions.append(f"strategy_id = ${idx}")
            params.append(strategy_id)
            idx += 1
        if fee_type:
            conditions.append(f"fee_type = ${idx}")
            params.append(fee_type.value)
            idx += 1
        if start:
            conditions.append(f"created_at >= ${idx}")
            params.append(start)
            idx += 1
        if end:
            conditions.append(f"created_at <= ${idx}")
            params.append(end)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT id, trade_id, strategy_id, fee_type, amount, currency, created_at
            FROM trading_fees
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [_row_to_dict(r) for r in rows]

    async def get_summary_by_strategy(
        self,
        strategy_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregate total fees grouped by strategy and fee type."""
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if strategy_id:
            conditions.append(f"strategy_id = ${idx}")
            params.append(strategy_id)
            idx += 1
        if start:
            conditions.append(f"created_at >= ${idx}")
            params.append(start)
            idx += 1
        if end:
            conditions.append(f"created_at <= ${idx}")
            params.append(end)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT strategy_id,
                   fee_type,
                   COUNT(*)        AS fee_count,
                   SUM(amount)     AS total_amount,
                   currency
            FROM trading_fees
            {where}
            GROUP BY strategy_id, fee_type, currency
            ORDER BY strategy_id, fee_type
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            {
                "strategy_id": r["strategy_id"],
                "fee_type": r["fee_type"],
                "fee_count": r["fee_count"],
                "total_amount": float(r["total_amount"]),
                "currency": r["currency"],
            }
            for r in rows
        ]

    async def get_fee_trend(
        self,
        strategy_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Daily fee totals for trend analysis."""
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if strategy_id:
            conditions.append(f"strategy_id = ${idx}")
            params.append(strategy_id)
            idx += 1
        if start:
            conditions.append(f"created_at >= ${idx}")
            params.append(start)
            idx += 1
        if end:
            conditions.append(f"created_at <= ${idx}")
            params.append(end)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT DATE(created_at) AS day,
                   SUM(amount)      AS total_fees,
                   COUNT(*)         AS fee_count
            FROM trading_fees
            {where}
            GROUP BY DATE(created_at)
            ORDER BY day
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            {
                "day": r["day"].isoformat(),
                "total_fees": float(r["total_fees"]),
                "fee_count": r["fee_count"],
            }
            for r in rows
        ]


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert an asyncpg Record to a serializable dict."""
    d = dict(row)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("amount") is not None:
        d["amount"] = float(d["amount"])
    return d
