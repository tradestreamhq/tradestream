"""
Risk calculation utilities for portfolio risk monitoring.

Provides VaR (Value at Risk), portfolio beta, correlation matrix,
and concentration alert computations.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def compute_exposure_by_asset(
    positions: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Compute current dollar exposure per asset from open positions."""
    exposure: Dict[str, float] = {}
    for p in positions:
        qty = float(p["quantity"])
        price = float(p["avg_entry_price"])
        exposure[p["symbol"]] = abs(qty * price)
    return exposure


def compute_concentration_alerts(
    exposure: Dict[str, float],
    threshold: float = 0.20,
) -> List[Dict[str, Any]]:
    """Return alerts for positions exceeding the concentration threshold."""
    total = sum(exposure.values())
    if total <= 0:
        return []
    alerts = []
    for symbol, exp in exposure.items():
        weight = exp / total
        if weight > threshold:
            alerts.append(
                {
                    "symbol": symbol,
                    "weight": round(weight, 4),
                    "exposure": round(exp, 2),
                    "threshold": threshold,
                }
            )
    return alerts


def compute_returns(pnl_series: List[float], exposures: List[float]) -> List[float]:
    """Convert a series of PnL values and exposures to percentage returns."""
    returns = []
    for pnl, exp in zip(pnl_series, exposures):
        if exp > 0:
            returns.append(pnl / exp)
        else:
            returns.append(0.0)
    return returns


def compute_var(
    returns: List[float],
    confidence: float = 0.95,
    current_exposure: float = 1.0,
) -> Optional[float]:
    """Compute historical Value at Risk at the given confidence level.

    Uses the historical simulation method: sort returns and take the
    percentile corresponding to (1 - confidence).
    """
    if len(returns) < 2:
        return None
    sorted_returns = sorted(returns)
    index = int(math.floor((1 - confidence) * len(sorted_returns)))
    index = max(0, min(index, len(sorted_returns) - 1))
    var_pct = sorted_returns[index]
    return round(abs(var_pct) * current_exposure, 2)


def compute_portfolio_beta(
    strategy_returns: List[float],
    benchmark_returns: List[float],
) -> Optional[float]:
    """Compute portfolio beta relative to a benchmark.

    beta = Cov(strategy, benchmark) / Var(benchmark)
    """
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return None
    sr = strategy_returns[:n]
    br = benchmark_returns[:n]
    mean_s = sum(sr) / n
    mean_b = sum(br) / n
    cov = sum((s - mean_s) * (b - mean_b) for s, b in zip(sr, br)) / (n - 1)
    var_b = sum((b - mean_b) ** 2 for b in br) / (n - 1)
    if var_b == 0:
        return None
    return round(cov / var_b, 4)


def compute_correlation_matrix(
    strategy_returns: Dict[str, List[float]],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise Pearson correlation between strategy return series.

    Returns a nested dict: {strategy_a: {strategy_b: correlation}}.
    """
    names = list(strategy_returns.keys())
    matrix: Dict[str, Dict[str, float]] = {}
    for a in names:
        matrix[a] = {}
        for b in names:
            matrix[a][b] = _pearson(strategy_returns[a], strategy_returns[b])
    return matrix


def _pearson(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient between two series."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x = x[:n]
    y = y[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if std_x == 0 or std_y == 0:
        return 0.0
    return round(cov / (std_x * std_y), 4)
