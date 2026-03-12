"""
PnL attribution logic — decomposes portfolio returns by strategy,
asset class, direction, realization status, and time period.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from services.pnl_attribution_api.models import (
    AssetAttribution,
    AttributionSummary,
    DirectionAttribution,
    Period,
    RealizationAttribution,
    StrategyAttribution,
    TimeBucket,
)

logger = logging.getLogger(__name__)

# SQL date_trunc granularity for each period
_TRUNC_MAP = {
    Period.DAILY: "day",
    Period.WEEKLY: "week",
    Period.MONTHLY: "month",
}


async def compute_attribution(
    conn: asyncpg.Connection,
    *,
    period: Period = Period.DAILY,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> AttributionSummary:
    """Compute full PnL attribution breakdown."""
    time_filter, params = _time_filter(start, end)

    by_strategy = await _strategy_attribution(conn, time_filter, params)
    by_asset = await _asset_attribution(conn, time_filter, params)
    by_direction = await _direction_attribution(conn, time_filter, params)
    realization = await _realization_attribution(conn, time_filter, params)
    by_time = await _time_attribution(conn, period, time_filter, params)

    total_pnl = realization.realized_pnl + realization.unrealized_pnl
    total_trades = sum(s.trade_count for s in by_strategy) if by_strategy else 0

    return AttributionSummary(
        total_pnl=total_pnl,
        total_trades=total_trades,
        by_strategy=by_strategy,
        by_asset=by_asset,
        by_direction=by_direction,
        realization=realization,
        by_time=by_time,
    )


def _time_filter(
    start: Optional[datetime], end: Optional[datetime]
) -> Tuple[str, List[Any]]:
    """Build WHERE clause fragments for time filtering on paper_trades."""
    clauses: List[str] = []
    params: List[Any] = []
    idx = 1

    if start:
        clauses.append(f"pt.opened_at >= ${idx}")
        params.append(start)
        idx += 1
    if end:
        clauses.append(f"pt.opened_at <= ${idx}")
        params.append(end)
        idx += 1

    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


async def _strategy_attribution(
    conn: asyncpg.Connection,
    time_filter: str,
    params: List[Any],
) -> List[StrategyAttribution]:
    query = f"""
        SELECT
            COALESCE(s.strategy_type, 'unknown') AS strategy_type,
            COUNT(*) AS trade_count,
            COALESCE(SUM(pt.pnl), 0) AS total_pnl,
            SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
            SUM(CASE WHEN pt.pnl <= 0 THEN 1 ELSE 0 END) AS losing_trades,
            COALESCE(AVG(CASE WHEN pt.pnl > 0 THEN pt.pnl END), 0) AS avg_win,
            COALESCE(AVG(CASE WHEN pt.pnl <= 0 THEN pt.pnl END), 0) AS avg_loss
        FROM paper_trades pt
        LEFT JOIN signals sig ON pt.signal_id = sig.id
        LEFT JOIN strategy_specs ss ON sig.spec_id = ss.id
        LEFT JOIN strategies s ON ss.strategy_id = s.strategy_id
        WHERE pt.status = 'CLOSED' {time_filter}
        GROUP BY s.strategy_type
        ORDER BY total_pnl DESC
    """
    rows = await conn.fetch(query, *params)

    grand_total = sum(float(r["total_pnl"]) for r in rows)

    results = []
    for r in rows:
        tc = int(r["trade_count"])
        wt = int(r["winning_trades"])
        lt = int(r["losing_trades"])
        total = float(r["total_pnl"])
        results.append(
            StrategyAttribution(
                strategy_type=r["strategy_type"],
                total_pnl=total,
                trade_count=tc,
                winning_trades=wt,
                losing_trades=lt,
                hit_rate=round(wt / tc, 4) if tc > 0 else 0.0,
                avg_win=float(r["avg_win"]),
                avg_loss=float(r["avg_loss"]),
                contribution_pct=round(total / grand_total, 4) if grand_total != 0 else 0.0,
            )
        )
    return results


async def _asset_attribution(
    conn: asyncpg.Connection,
    time_filter: str,
    params: List[Any],
) -> List[AssetAttribution]:
    query = f"""
        SELECT
            pt.symbol,
            COUNT(*) AS trade_count,
            COALESCE(SUM(pt.pnl), 0) AS total_pnl
        FROM paper_trades pt
        WHERE pt.status = 'CLOSED' {time_filter}
        GROUP BY pt.symbol
        ORDER BY total_pnl DESC
    """
    rows = await conn.fetch(query, *params)
    grand_total = sum(float(r["total_pnl"]) for r in rows)

    return [
        AssetAttribution(
            symbol=r["symbol"],
            total_pnl=float(r["total_pnl"]),
            trade_count=int(r["trade_count"]),
            contribution_pct=round(float(r["total_pnl"]) / grand_total, 4)
            if grand_total != 0
            else 0.0,
        )
        for r in rows
    ]


async def _direction_attribution(
    conn: asyncpg.Connection,
    time_filter: str,
    params: List[Any],
) -> List[DirectionAttribution]:
    query = f"""
        SELECT
            pt.side,
            COUNT(*) AS trade_count,
            COALESCE(SUM(pt.pnl), 0) AS total_pnl
        FROM paper_trades pt
        WHERE pt.status = 'CLOSED' {time_filter}
        GROUP BY pt.side
        ORDER BY total_pnl DESC
    """
    rows = await conn.fetch(query, *params)
    grand_total = sum(float(r["total_pnl"]) for r in rows)

    return [
        DirectionAttribution(
            side=r["side"],
            total_pnl=float(r["total_pnl"]),
            trade_count=int(r["trade_count"]),
            contribution_pct=round(float(r["total_pnl"]) / grand_total, 4)
            if grand_total != 0
            else 0.0,
        )
        for r in rows
    ]


async def _realization_attribution(
    conn: asyncpg.Connection,
    time_filter: str,
    params: List[Any],
) -> RealizationAttribution:
    realized_query = f"""
        SELECT COALESCE(SUM(pt.pnl), 0) AS realized_pnl
        FROM paper_trades pt
        WHERE pt.status = 'CLOSED' {time_filter}
    """
    unrealized_query = """
        SELECT COALESCE(SUM(unrealized_pnl), 0) AS unrealized_pnl
        FROM paper_portfolio
    """
    realized_row = await conn.fetchrow(realized_query, *params)
    unrealized_row = await conn.fetchrow(unrealized_query)

    realized = float(realized_row["realized_pnl"])
    unrealized = float(unrealized_row["unrealized_pnl"])
    return RealizationAttribution(
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        total_pnl=realized + unrealized,
    )


async def _time_attribution(
    conn: asyncpg.Connection,
    period: Period,
    time_filter: str,
    params: List[Any],
) -> List[TimeBucket]:
    trunc = _TRUNC_MAP[period]
    query = f"""
        SELECT
            date_trunc('{trunc}', pt.closed_at) AS bucket,
            COUNT(*) AS trade_count,
            COALESCE(SUM(pt.pnl), 0) AS total_pnl,
            SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
            SUM(CASE WHEN pt.pnl <= 0 THEN 1 ELSE 0 END) AS losing_trades
        FROM paper_trades pt
        WHERE pt.status = 'CLOSED' AND pt.closed_at IS NOT NULL {time_filter}
        GROUP BY bucket
        ORDER BY bucket DESC
    """
    rows = await conn.fetch(query, *params)

    return [
        TimeBucket(
            period=r["bucket"].isoformat() if r["bucket"] else "unknown",
            total_pnl=float(r["total_pnl"]),
            trade_count=int(r["trade_count"]),
            winning_trades=int(r["winning_trades"]),
            losing_trades=int(r["losing_trades"]),
        )
        for r in rows
    ]
