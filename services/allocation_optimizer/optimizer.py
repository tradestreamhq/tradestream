"""
Mean-variance (Markowitz) portfolio optimizer.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize

from services.allocation_optimizer.covariance import (
    compute_covariance_matrix,
    compute_mean_returns,
    shrink_covariance,
)
from services.allocation_optimizer.models import (
    EfficientFrontierPoint,
    EfficientFrontierResponse,
    OptimizationResult,
)

logger = logging.getLogger(__name__)


def _portfolio_stats(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float,
) -> Tuple[float, float, float]:
    """Compute portfolio expected return, volatility, and Sharpe ratio."""
    port_return = weights @ mean_returns
    port_vol = np.sqrt(weights @ cov_matrix @ weights)
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0.0
    return float(port_return), float(port_vol), float(sharpe)


def _build_constraints_and_bounds(
    n: int,
    min_weight: float,
    max_weight: float,
    target_return: Optional[float] = None,
    mean_returns: Optional[np.ndarray] = None,
) -> Tuple[list, list]:
    """Build scipy constraints and bounds."""
    bounds = [(min_weight, max_weight)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    if target_return is not None and mean_returns is not None:
        constraints.append(
            {
                "type": "eq",
                "fun": lambda w, mu=mean_returns, tr=target_return: w @ mu - tr,
            }
        )

    return constraints, bounds


def optimize_max_sharpe(
    strategy_ids: List[str],
    returns_matrix: np.ndarray,
    risk_free_rate: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> OptimizationResult:
    """Find weights that maximize the Sharpe ratio."""
    n = returns_matrix.shape[1]
    mean_ret = compute_mean_returns(returns_matrix)
    cov = shrink_covariance(compute_covariance_matrix(returns_matrix))

    def neg_sharpe(w):
        ret = w @ mean_ret
        vol = np.sqrt(w @ cov @ w)
        return -(ret - risk_free_rate) / vol if vol > 1e-12 else 0.0

    constraints, bounds = _build_constraints_and_bounds(n, min_weight, max_weight)
    x0 = np.full(n, 1.0 / n)

    result = minimize(
        neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints
    )
    weights = result.x
    ret, vol, sharpe = _portfolio_stats(weights, mean_ret, cov, risk_free_rate)

    return OptimizationResult(
        weights={sid: round(float(w), 6) for sid, w in zip(strategy_ids, weights)},
        expected_return=round(ret, 6),
        volatility=round(vol, 6),
        sharpe_ratio=round(sharpe, 6),
    )


def optimize_min_variance(
    strategy_ids: List[str],
    returns_matrix: np.ndarray,
    risk_free_rate: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> OptimizationResult:
    """Find the minimum variance portfolio."""
    n = returns_matrix.shape[1]
    mean_ret = compute_mean_returns(returns_matrix)
    cov = shrink_covariance(compute_covariance_matrix(returns_matrix))

    def variance(w):
        return w @ cov @ w

    constraints, bounds = _build_constraints_and_bounds(n, min_weight, max_weight)
    x0 = np.full(n, 1.0 / n)

    result = minimize(
        variance, x0, method="SLSQP", bounds=bounds, constraints=constraints
    )
    weights = result.x
    ret, vol, sharpe = _portfolio_stats(weights, mean_ret, cov, risk_free_rate)

    return OptimizationResult(
        weights={sid: round(float(w), 6) for sid, w in zip(strategy_ids, weights)},
        expected_return=round(ret, 6),
        volatility=round(vol, 6),
        sharpe_ratio=round(sharpe, 6),
    )


def optimize_target_return(
    strategy_ids: List[str],
    returns_matrix: np.ndarray,
    target_return: float,
    risk_free_rate: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> OptimizationResult:
    """Find minimum variance portfolio achieving a target return."""
    n = returns_matrix.shape[1]
    mean_ret = compute_mean_returns(returns_matrix)
    cov = shrink_covariance(compute_covariance_matrix(returns_matrix))

    def variance(w):
        return w @ cov @ w

    constraints, bounds = _build_constraints_and_bounds(
        n, min_weight, max_weight, target_return, mean_ret
    )
    x0 = np.full(n, 1.0 / n)

    result = minimize(
        variance, x0, method="SLSQP", bounds=bounds, constraints=constraints
    )
    weights = result.x
    ret, vol, sharpe = _portfolio_stats(weights, mean_ret, cov, risk_free_rate)

    return OptimizationResult(
        weights={sid: round(float(w), 6) for sid, w in zip(strategy_ids, weights)},
        expected_return=round(ret, 6),
        volatility=round(vol, 6),
        sharpe_ratio=round(sharpe, 6),
    )


def compute_efficient_frontier(
    strategy_ids: List[str],
    returns_matrix: np.ndarray,
    risk_free_rate: float = 0.0,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    n_points: int = 20,
) -> EfficientFrontierResponse:
    """Compute the efficient frontier and identify the optimal portfolio."""
    mean_ret = compute_mean_returns(returns_matrix)

    # Find min and max feasible returns
    min_var = optimize_min_variance(
        strategy_ids, returns_matrix, risk_free_rate, min_weight, max_weight
    )
    min_feasible_return = min_var.expected_return

    # Max return is the return of the highest-return strategy (within weight bounds)
    max_feasible_return = float(np.max(mean_ret))

    if min_feasible_return >= max_feasible_return:
        # Degenerate case — single point frontier
        point = EfficientFrontierPoint(
            expected_return=min_var.expected_return,
            volatility=min_var.volatility,
            sharpe_ratio=min_var.sharpe_ratio,
            weights=min_var.weights,
        )
        return EfficientFrontierResponse(
            points=[point],
            optimal=min_var,
        )

    target_returns = np.linspace(min_feasible_return, max_feasible_return, n_points)
    points: List[EfficientFrontierPoint] = []
    best_sharpe = -np.inf
    optimal = min_var

    for target in target_returns:
        try:
            result = optimize_target_return(
                strategy_ids,
                returns_matrix,
                float(target),
                risk_free_rate,
                min_weight,
                max_weight,
            )
            point = EfficientFrontierPoint(
                expected_return=result.expected_return,
                volatility=result.volatility,
                sharpe_ratio=result.sharpe_ratio,
                weights=result.weights,
            )
            points.append(point)
            if result.sharpe_ratio > best_sharpe:
                best_sharpe = result.sharpe_ratio
                optimal = result
        except Exception:
            logger.debug("Skipping infeasible target return %.6f", target)

    return EfficientFrontierResponse(points=points, optimal=optimal)
