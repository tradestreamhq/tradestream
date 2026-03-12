"""Strategy parameter optimizer using grid search over backtesting results."""

import logging
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner
from services.param_optimizer.grid import ParameterGrid
from services.param_optimizer.models import (
    OptimizationResult,
    ParameterRange,
    ParameterSetResult,
)

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Grid search optimizer for strategy parameters.

    Evaluates every combination in the parameter grid using backtesting,
    then ranks results by Sharpe ratio with an optional drawdown constraint.

    Args:
        runner: VectorBTRunner instance (creates one if not provided).
        max_drawdown_limit: Discard results with max_drawdown exceeding this.
        top_n: Number of top results to return.
        rank_key: Metric name to rank by (default: sharpe_ratio).
    """

    def __init__(
        self,
        runner: Optional[VectorBTRunner] = None,
        max_drawdown_limit: float = 1.0,
        top_n: int = 10,
        rank_key: str = "sharpe_ratio",
    ):
        self._runner = runner or VectorBTRunner()
        self._max_drawdown_limit = max_drawdown_limit
        self._top_n = top_n
        self._rank_key = rank_key

    def optimize(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        param_ranges: List[ParameterRange],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> OptimizationResult:
        """Run grid search optimization.

        Args:
            ohlcv: OHLCV DataFrame for backtesting.
            strategy_name: Strategy to optimize (e.g. "SMA_RSI").
            param_ranges: Parameter search spaces.
            progress_callback: Optional fn(completed, total) called after each run.

        Returns:
            OptimizationResult with ranked parameter sets.
        """
        grid = ParameterGrid(param_ranges)
        combos = grid.generate()
        total = len(combos)

        logger.info(
            "Starting grid search for %s: %d combinations", strategy_name, total
        )

        all_results: List[ParameterSetResult] = []

        # Use batch API for efficiency
        metrics_list = self._runner.run_batch(ohlcv, strategy_name, combos)

        for i, (params, metrics) in enumerate(zip(combos, metrics_list)):
            all_results.append(ParameterSetResult(parameters=params, metrics=metrics))
            if progress_callback:
                progress_callback(i + 1, total)

        # Apply drawdown constraint and rank
        top_results = self._rank_results(all_results)

        logger.info(
            "Grid search complete: %d/%d passed drawdown filter (limit=%.2f)",
            len(top_results),
            total,
            self._max_drawdown_limit,
        )

        return OptimizationResult(
            strategy_name=strategy_name,
            total_combinations=total,
            top_results=top_results[: self._top_n],
            all_results=all_results,
            max_drawdown_limit=self._max_drawdown_limit,
        )

    def _rank_results(
        self, results: List[ParameterSetResult]
    ) -> List[ParameterSetResult]:
        """Filter by drawdown constraint and sort by rank_key descending."""
        filtered = [
            r for r in results if r.metrics.max_drawdown <= self._max_drawdown_limit
        ]

        filtered.sort(key=lambda r: getattr(r.metrics, self._rank_key), reverse=True)

        return filtered
