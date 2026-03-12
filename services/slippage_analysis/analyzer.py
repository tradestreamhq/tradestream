"""
Slippage analysis engine.

Compares expected vs actual execution prices across trades,
calculates slippage metrics, and identifies adverse patterns.
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Thresholds for size buckets (in USD notional value)
SMALL_THRESHOLD = 1000.0
LARGE_THRESHOLD = 10000.0

# Threshold for adverse pattern detection (basis points)
ADVERSE_SLIPPAGE_THRESHOLD = 10.0


def classify_size_bucket(order_size: float, price: float) -> str:
    notional = order_size * price
    if notional < SMALL_THRESHOLD:
        return "small"
    elif notional < LARGE_THRESHOLD:
        return "medium"
    return "large"


def compute_slippage_bps(expected_price: float, fill_price: float, side: str) -> float:
    """Compute slippage in basis points. Positive = adverse (worse fill)."""
    if expected_price == 0:
        return 0.0
    if side == "BUY":
        return ((fill_price - expected_price) / expected_price) * 10000.0
    else:
        return ((expected_price - fill_price) / expected_price) * 10000.0


async def fetch_slippage_records(
    conn: asyncpg.Connection,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fetch trade records with slippage data from the database."""
    conditions = ["t.expected_price IS NOT NULL", "t.fill_price IS NOT NULL"]
    params: list = []
    idx = 1

    if symbol:
        conditions.append(f"t.symbol = ${idx}")
        params.append(symbol)
        idx += 1
    if side:
        conditions.append(f"t.side = ${idx}")
        params.append(side)
        idx += 1
    if start_date:
        conditions.append(f"t.filled_at >= ${idx}::timestamptz")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"t.filled_at <= ${idx}::timestamptz")
        params.append(end_date)
        idx += 1

    where = " AND ".join(conditions)
    query = f"""
        SELECT t.id as trade_id, t.symbol, t.side,
               t.expected_price, t.fill_price, t.quantity as order_size,
               t.filled_at
        FROM paper_trades t
        WHERE {where}
        ORDER BY t.filled_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    records = []
    for row in rows:
        r = dict(row)
        expected = float(r["expected_price"])
        fill = float(r["fill_price"])
        size = float(r["order_size"])
        side_val = r["side"]
        slippage = compute_slippage_bps(expected, fill, side_val)
        filled_at = r["filled_at"]

        records.append({
            "trade_id": str(r["trade_id"]),
            "symbol": r["symbol"],
            "side": side_val,
            "expected_price": expected,
            "fill_price": fill,
            "order_size": size,
            "slippage_bps": round(slippage, 2),
            "filled_at": filled_at.isoformat() if hasattr(filled_at, "isoformat") else str(filled_at),
            "hour_of_day": filled_at.hour if hasattr(filled_at, "hour") else 0,
            "size_bucket": classify_size_bucket(size, expected),
        })
    return records


async def count_slippage_records(
    conn: asyncpg.Connection,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """Count trade records with slippage data."""
    conditions = ["t.expected_price IS NOT NULL", "t.fill_price IS NOT NULL"]
    params: list = []
    idx = 1

    if symbol:
        conditions.append(f"t.symbol = ${idx}")
        params.append(symbol)
        idx += 1
    if side:
        conditions.append(f"t.side = ${idx}")
        params.append(side)
        idx += 1
    if start_date:
        conditions.append(f"t.filled_at >= ${idx}::timestamptz")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"t.filled_at <= ${idx}::timestamptz")
        params.append(end_date)
        idx += 1

    where = " AND ".join(conditions)
    query = f"SELECT COUNT(*) FROM paper_trades t WHERE {where}"
    return await conn.fetchval(query, *params)


def compute_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate slippage summary from records."""
    if not records:
        return {
            "total_trades": 0,
            "avg_slippage_bps": 0.0,
            "median_slippage_bps": 0.0,
            "worst_slippage_bps": 0.0,
            "total_slippage_cost": 0.0,
        }

    slippages = [r["slippage_bps"] for r in records]
    slippages_sorted = sorted(slippages)
    n = len(slippages_sorted)
    median = (
        slippages_sorted[n // 2]
        if n % 2 == 1
        else (slippages_sorted[n // 2 - 1] + slippages_sorted[n // 2]) / 2.0
    )

    total_cost = sum(
        abs(r["fill_price"] - r["expected_price"]) * r["order_size"] for r in records
    )

    return {
        "total_trades": n,
        "avg_slippage_bps": round(sum(slippages) / n, 2),
        "median_slippage_bps": round(median, 2),
        "worst_slippage_bps": round(max(slippages), 2),
        "total_slippage_cost": round(total_cost, 2),
    }


def compute_by_symbol(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group slippage metrics by symbol."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        groups.setdefault(r["symbol"], []).append(r)

    result = []
    for symbol, group in sorted(groups.items()):
        slippages = [r["slippage_bps"] for r in group]
        cost = sum(abs(r["fill_price"] - r["expected_price"]) * r["order_size"] for r in group)
        result.append({
            "symbol": symbol,
            "trade_count": len(group),
            "avg_slippage_bps": round(sum(slippages) / len(slippages), 2),
            "total_slippage_cost": round(cost, 2),
        })
    return result


def compute_by_hour(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group slippage metrics by hour of day."""
    groups: Dict[int, List[float]] = {}
    for r in records:
        groups.setdefault(r["hour_of_day"], []).append(r["slippage_bps"])

    result = []
    for hour in sorted(groups.keys()):
        slippages = groups[hour]
        result.append({
            "hour": hour,
            "trade_count": len(slippages),
            "avg_slippage_bps": round(sum(slippages) / len(slippages), 2),
        })
    return result


def compute_by_size_bucket(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group slippage metrics by order size bucket."""
    groups: Dict[str, List[float]] = {}
    for r in records:
        groups.setdefault(r["size_bucket"], []).append(r["slippage_bps"])

    result = []
    for bucket in ["small", "medium", "large"]:
        if bucket in groups:
            slippages = groups[bucket]
            result.append({
                "bucket": bucket,
                "trade_count": len(slippages),
                "avg_slippage_bps": round(sum(slippages) / len(slippages), 2),
            })
    return result


def detect_adverse_patterns(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify adverse slippage patterns."""
    patterns = []

    if not records:
        return patterns

    # Pattern 1: High slippage at market open (hours 9-10 UTC)
    open_trades = [r for r in records if r["hour_of_day"] in (9, 10)]
    if open_trades:
        avg_open = sum(r["slippage_bps"] for r in open_trades) / len(open_trades)
        avg_all = sum(r["slippage_bps"] for r in records) / len(records)
        if avg_open > avg_all + ADVERSE_SLIPPAGE_THRESHOLD and len(open_trades) >= 3:
            severity = "high" if avg_open > avg_all * 2 else "medium"
            patterns.append({
                "pattern_type": "market_open_slippage",
                "description": (
                    f"Avg slippage at market open ({avg_open:.1f} bps) is significantly "
                    f"higher than overall avg ({avg_all:.1f} bps)"
                ),
                "severity": severity,
                "affected_trades": len(open_trades),
                "avg_slippage_bps": round(avg_open, 2),
            })

    # Pattern 2: Large orders get worse fills
    large_trades = [r for r in records if r["size_bucket"] == "large"]
    small_trades = [r for r in records if r["size_bucket"] == "small"]
    if large_trades and small_trades:
        avg_large = sum(r["slippage_bps"] for r in large_trades) / len(large_trades)
        avg_small = sum(r["slippage_bps"] for r in small_trades) / len(small_trades)
        if avg_large > avg_small + ADVERSE_SLIPPAGE_THRESHOLD and len(large_trades) >= 3:
            severity = "high" if avg_large > avg_small * 2 else "medium"
            patterns.append({
                "pattern_type": "size_impact",
                "description": (
                    f"Large orders avg {avg_large:.1f} bps slippage vs "
                    f"{avg_small:.1f} bps for small orders"
                ),
                "severity": severity,
                "affected_trades": len(large_trades),
                "avg_slippage_bps": round(avg_large, 2),
            })

    # Pattern 3: Symbol with consistently high slippage
    by_symbol = compute_by_symbol(records)
    avg_all = sum(r["slippage_bps"] for r in records) / len(records)
    for sym in by_symbol:
        if (
            sym["avg_slippage_bps"] > avg_all + ADVERSE_SLIPPAGE_THRESHOLD
            and sym["trade_count"] >= 3
        ):
            patterns.append({
                "pattern_type": "symbol_adverse",
                "description": (
                    f"{sym['symbol']} has avg slippage of {sym['avg_slippage_bps']:.1f} bps, "
                    f"well above overall avg of {avg_all:.1f} bps"
                ),
                "severity": "medium",
                "affected_trades": sym["trade_count"],
                "avg_slippage_bps": sym["avg_slippage_bps"],
            })

    return patterns


def build_report(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a complete slippage analysis report from records."""
    return {
        "summary": compute_summary(records),
        "by_symbol": compute_by_symbol(records),
        "by_hour": compute_by_hour(records),
        "by_size_bucket": compute_by_size_bucket(records),
        "adverse_patterns": detect_adverse_patterns(records),
    }
