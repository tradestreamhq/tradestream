"""Benchmark comparison calculations.

Compares strategy return series against benchmark return series,
computing alpha, beta, information ratio, and tracking error.
"""

import math
from datetime import datetime, timezone

import numpy as np

from services.benchmark_comparison.models import (
    BenchmarkComparison,
    BenchmarkMetrics,
    ReturnSeries,
    TimePeriod,
)

ANNUALIZATION_FACTOR = 252  # trading days per year


def compute_metrics(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
) -> BenchmarkMetrics:
    """Compute benchmark comparison metrics from daily return arrays.

    Args:
        strategy_returns: Array of daily strategy returns (fractional, e.g. 0.01 = 1%).
        benchmark_returns: Array of daily benchmark returns (fractional).

    Returns:
        BenchmarkMetrics with alpha, beta, information ratio, tracking error, etc.
    """
    if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
        return BenchmarkMetrics(
            alpha=0.0,
            beta=0.0,
            information_ratio=0.0,
            tracking_error=0.0,
            strategy_return=0.0,
            benchmark_return=0.0,
            excess_return=0.0,
            correlation=0.0,
        )

    n = min(len(strategy_returns), len(benchmark_returns))
    strat = strategy_returns[:n]
    bench = benchmark_returns[:n]

    # Total compounded returns
    strategy_total = float(np.prod(1 + strat) - 1)
    benchmark_total = float(np.prod(1 + bench) - 1)
    excess_return = strategy_total - benchmark_total

    # Beta via covariance / variance
    bench_var = float(np.var(bench, ddof=1))
    if bench_var > 0:
        cov = float(np.cov(strat, bench, ddof=1)[0, 1])
        beta = cov / bench_var
    else:
        beta = 0.0

    # Annualized alpha: (strategy mean - beta * benchmark mean) * 252
    strat_mean = float(np.mean(strat))
    bench_mean = float(np.mean(bench))
    alpha = (strat_mean - beta * bench_mean) * ANNUALIZATION_FACTOR

    # Tracking error: annualized std of excess returns
    excess_daily = strat - bench
    tracking_error = float(np.std(excess_daily, ddof=1)) * math.sqrt(
        ANNUALIZATION_FACTOR
    )

    # Information ratio: annualized mean excess / tracking error
    mean_excess = float(np.mean(excess_daily))
    if tracking_error > 0:
        information_ratio = (mean_excess * ANNUALIZATION_FACTOR) / tracking_error
    else:
        information_ratio = 0.0

    # Correlation
    if np.std(strat) > 0 and np.std(bench) > 0:
        correlation = float(np.corrcoef(strat, bench)[0, 1])
    else:
        correlation = 0.0

    return BenchmarkMetrics(
        alpha=round(alpha, 6),
        beta=round(beta, 6),
        information_ratio=round(information_ratio, 6),
        tracking_error=round(tracking_error, 6),
        strategy_return=round(strategy_total * 100, 4),
        benchmark_return=round(benchmark_total * 100, 4),
        excess_return=round(excess_return * 100, 4),
        correlation=round(correlation, 6),
    )


def compare(
    strategy_id: str,
    benchmark_name: str,
    period: TimePeriod,
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
) -> BenchmarkComparison:
    """Build a full BenchmarkComparison result."""
    metrics = compute_metrics(strategy_returns, benchmark_returns)
    return BenchmarkComparison(
        strategy_id=strategy_id,
        benchmark=benchmark_name,
        period=period,
        metrics=metrics,
        computed_at=datetime.now(timezone.utc),
    )
