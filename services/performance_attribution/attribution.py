"""
Core attribution calculation functions.

Provides Sharpe ratio, max drawdown, win rate, and daily return
aggregation from trade-level P&L data.
"""

import math
from collections import defaultdict
from typing import Dict, List, Optional


def compute_win_rate(pnls: List[float]) -> Optional[float]:
    """Calculate win rate from a list of P&L values.

    Returns None if no trades.
    """
    if not pnls:
        return None
    winners = sum(1 for p in pnls if p > 0)
    return round(winners / len(pnls), 4)


def compute_max_drawdown(pnls: List[float]) -> Optional[float]:
    """Calculate max drawdown from cumulative P&L series.

    Returns a non-positive value representing the worst peak-to-trough
    decline. Returns None if no trades.
    """
    if not pnls:
        return None

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0

    for pnl in pnls:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        drawdown = cumulative - peak
        if drawdown < max_dd:
            max_dd = drawdown

    return round(max_dd, 8)


def compute_daily_returns(trades: List[Dict]) -> List[float]:
    """Aggregate trade P&Ls into daily returns based on closed_at date.

    Trades without closed_at are skipped. Returns a list of daily
    return values sorted chronologically.
    """
    daily: Dict[str, float] = defaultdict(float)
    for t in trades:
        closed = t.get("closed_at")
        if closed is None:
            continue
        day_key = closed.date().isoformat() if hasattr(closed, "date") else str(closed)[:10]
        daily[day_key] += float(t["pnl"])

    return [daily[k] for k in sorted(daily.keys())]


def compute_sharpe_ratio(
    daily_returns: List[float], risk_free_rate: float = 0.0
) -> Optional[float]:
    """Calculate annualized Sharpe ratio from daily returns.

    Uses the standard formula: (mean - rf) / std * sqrt(252).
    Returns None if fewer than 2 data points or zero standard deviation.
    """
    if len(daily_returns) < 2:
        return None

    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = math.sqrt(variance)

    if std == 0:
        return None

    sharpe = ((mean - risk_free_rate) / std) * math.sqrt(252)
    result = round(sharpe, 4)

    if math.isnan(result) or math.isinf(result):
        return None
    return result
