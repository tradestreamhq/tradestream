"""
Portfolio Risk Analytics — core calculations.

Provides portfolio-level risk metrics aggregated across strategies:
VaR (historical simulation), drawdown, Sharpe/Sortino ratios,
concentration risk, and strategy correlation.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np


@dataclass
class StrategyReturn:
    """Daily returns for a single strategy."""

    strategy_id: str
    returns: List[float]
    capital_allocated: float = 0.0


@dataclass
class RiskSnapshot:
    """Portfolio-level risk snapshot."""

    total_exposure: float = 0.0
    net_position: float = 0.0
    portfolio_value: float = 0.0
    var_95: Optional[float] = None
    var_99: Optional[float] = None
    max_drawdown: Optional[float] = None
    current_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    strategy_concentrations: Dict[str, float] = field(default_factory=dict)
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    strategy_count: int = 0


def compute_var(returns: Sequence[float], confidence: float = 0.95) -> Optional[float]:
    """Compute Value at Risk using historical simulation.

    Args:
        returns: Sequence of portfolio returns (as fractions, e.g. 0.01 = 1%).
        confidence: Confidence level (0.95 for 95% VaR).

    Returns:
        VaR as a positive number representing potential loss, or None if
        insufficient data.
    """
    if len(returns) < 2:
        return None
    arr = np.array(returns, dtype=np.float64)
    percentile = (1 - confidence) * 100
    var_value = float(np.percentile(arr, percentile))
    return -var_value if var_value < 0 else 0.0


def compute_max_drawdown(equity_curve: Sequence[float]) -> Optional[float]:
    """Compute maximum drawdown from an equity curve.

    Args:
        equity_curve: Sequence of portfolio values over time.

    Returns:
        Max drawdown as a positive fraction (0.10 = 10%), or None if
        insufficient data.
    """
    if len(equity_curve) < 2:
        return None
    arr = np.array(equity_curve, dtype=np.float64)
    peak = np.maximum.accumulate(arr)
    drawdowns = (peak - arr) / np.where(peak > 0, peak, 1.0)
    return float(np.max(drawdowns))


def compute_current_drawdown(equity_curve: Sequence[float]) -> Optional[float]:
    """Compute current drawdown from peak."""
    if len(equity_curve) < 1:
        return None
    arr = np.array(equity_curve, dtype=np.float64)
    peak = float(np.max(arr))
    if peak <= 0:
        return None
    current = float(arr[-1])
    return (peak - current) / peak


def compute_sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Compute annualized Sharpe ratio.

    Args:
        returns: Sequence of periodic returns.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Number of return periods per year (252 for daily).

    Returns:
        Annualized Sharpe ratio, or None if insufficient data.
    """
    if len(returns) < 2:
        return None
    arr = np.array(returns, dtype=np.float64)
    periodic_rf = risk_free_rate / periods_per_year
    excess = arr - periodic_rf
    mean_excess = float(np.mean(excess))
    std = float(np.std(excess, ddof=1))
    if std == 0:
        return None
    return (mean_excess / std) * math.sqrt(periods_per_year)


def compute_sortino_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Compute annualized Sortino ratio (downside deviation only).

    Args:
        returns: Sequence of periodic returns.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Number of return periods per year.

    Returns:
        Annualized Sortino ratio, or None if insufficient data.
    """
    if len(returns) < 2:
        return None
    arr = np.array(returns, dtype=np.float64)
    periodic_rf = risk_free_rate / periods_per_year
    excess = arr - periodic_rf
    mean_excess = float(np.mean(excess))
    downside = excess[excess < 0]
    if len(downside) == 0:
        return None
    downside_std = float(np.sqrt(np.mean(downside**2)))
    if downside_std == 0:
        return None
    return (mean_excess / downside_std) * math.sqrt(periods_per_year)


def compute_concentration(
    allocations: Dict[str, float],
) -> Dict[str, float]:
    """Compute strategy concentration as fraction of total capital.

    Args:
        allocations: Map of strategy_id -> capital allocated.

    Returns:
        Map of strategy_id -> fraction of total.
    """
    total = sum(abs(v) for v in allocations.values())
    if total == 0:
        return {k: 0.0 for k in allocations}
    return {k: round(abs(v) / total, 4) for k, v in allocations.items()}


def compute_correlation_matrix(
    strategy_returns: List[StrategyReturn],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise correlation matrix between strategy returns.

    Args:
        strategy_returns: List of StrategyReturn objects with aligned return
        series (same length and dates).

    Returns:
        Nested dict mapping strategy pairs to correlation coefficients.
    """
    if len(strategy_returns) < 2:
        result: Dict[str, Dict[str, float]] = {}
        for sr in strategy_returns:
            result[sr.strategy_id] = {sr.strategy_id: 1.0}
        return result

    # Build matrix (rows = strategies, cols = time periods)
    min_len = min(len(sr.returns) for sr in strategy_returns)
    if min_len < 2:
        result = {}
        for sr in strategy_returns:
            result[sr.strategy_id] = {
                sr2.strategy_id: (1.0 if sr.strategy_id == sr2.strategy_id else 0.0)
                for sr2 in strategy_returns
            }
        return result

    matrix = np.array(
        [sr.returns[:min_len] for sr in strategy_returns], dtype=np.float64
    )
    corr = np.corrcoef(matrix)

    result = {}
    for i, sr_i in enumerate(strategy_returns):
        result[sr_i.strategy_id] = {}
        for j, sr_j in enumerate(strategy_returns):
            val = float(corr[i, j])
            result[sr_i.strategy_id][sr_j.strategy_id] = round(val, 4)
    return result


def compute_portfolio_returns(
    strategy_returns: List[StrategyReturn],
) -> List[float]:
    """Compute weighted portfolio returns from strategy returns.

    Weights are based on capital_allocated. If no capital info is available,
    equal-weights all strategies.
    """
    if not strategy_returns:
        return []

    total_capital = sum(sr.capital_allocated for sr in strategy_returns)

    min_len = min(len(sr.returns) for sr in strategy_returns)
    if min_len == 0:
        return []

    portfolio = np.zeros(min_len, dtype=np.float64)
    for sr in strategy_returns:
        weight = (
            sr.capital_allocated / total_capital
            if total_capital > 0
            else 1.0 / len(strategy_returns)
        )
        arr = np.array(sr.returns[:min_len], dtype=np.float64)
        portfolio += weight * arr

    return portfolio.tolist()


def build_risk_snapshot(
    strategy_returns: List[StrategyReturn],
    portfolio_value: float,
) -> RiskSnapshot:
    """Build a complete risk snapshot from strategy return data.

    Args:
        strategy_returns: Per-strategy return series with capital allocations.
        portfolio_value: Current total portfolio value.

    Returns:
        RiskSnapshot with all computed metrics.
    """
    allocations = {sr.strategy_id: sr.capital_allocated for sr in strategy_returns}
    total_exposure = sum(abs(v) for v in allocations.values())
    net_position = sum(v for v in allocations.values())

    port_returns = compute_portfolio_returns(strategy_returns)

    # Build equity curve from returns
    equity_curve = [portfolio_value]
    if port_returns:
        val = portfolio_value
        for r in reversed(port_returns):
            val = val / (1 + r) if (1 + r) != 0 else val
            equity_curve.insert(0, val)

    snapshot = RiskSnapshot(
        total_exposure=total_exposure,
        net_position=net_position,
        portfolio_value=portfolio_value,
        var_95=compute_var(port_returns, 0.95),
        var_99=compute_var(port_returns, 0.99),
        max_drawdown=compute_max_drawdown(equity_curve),
        current_drawdown=compute_current_drawdown(equity_curve),
        sharpe_ratio=compute_sharpe_ratio(port_returns),
        sortino_ratio=compute_sortino_ratio(port_returns),
        strategy_concentrations=compute_concentration(allocations),
        correlation_matrix=compute_correlation_matrix(strategy_returns),
        strategy_count=len(strategy_returns),
    )
    return snapshot
