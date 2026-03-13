"""
Grid Search Strategy Optimizer.

Generates all parameter combinations from defined ranges,
runs backtests for each, and ranks results by Sharpe ratio.
"""

import itertools
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner

logger = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """Defines a parameter range for grid search."""

    name: str
    min_value: float
    max_value: float
    step: float

    def values(self) -> List[float]:
        """Generate all values in the range."""
        result = []
        v = self.min_value
        while v <= self.max_value + 1e-9:
            result.append(v)
            v += self.step
        return result


@dataclass
class GridSearchResult:
    """Result of a single parameter combination backtest."""

    parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    rank: int = 0


@dataclass
class GridSearchConfig:
    """Configuration for a grid search optimization run."""

    strategy_name: str
    parameter_ranges: List[ParameterRange]
    top_n: int = 10

    @property
    def total_combinations(self) -> int:
        counts = [len(pr.values()) for pr in self.parameter_ranges]
        result = 1
        for c in counts:
            result *= c
        return result


class GridSearchOptimizer:
    """Runs grid search over backtesting engine to find optimal parameters."""

    def __init__(self, runner: Optional[VectorBTRunner] = None):
        self.runner = runner or VectorBTRunner()

    def generate_parameter_grid(
        self, parameter_ranges: List[ParameterRange]
    ) -> List[Dict[str, Any]]:
        """Generate all parameter combinations from ranges."""
        if not parameter_ranges:
            return [{}]

        names = [pr.name for pr in parameter_ranges]
        value_lists = [pr.values() for pr in parameter_ranges]

        grid = []
        for combo in itertools.product(*value_lists):
            params = {}
            for name, value in zip(names, combo):
                # Use int if value is whole number
                params[name] = int(value) if value == int(value) else value
            grid.append(params)

        return grid

    def run(self, ohlcv, config: GridSearchConfig) -> List[GridSearchResult]:
        """
        Run grid search optimization.

        Args:
            ohlcv: DataFrame with OHLCV data
            config: Grid search configuration

        Returns:
            Top N results ranked by Sharpe ratio
        """
        grid = self.generate_parameter_grid(config.parameter_ranges)
        logger.info(
            "Running grid search: %d combinations for %s",
            len(grid),
            config.strategy_name,
        )

        results: List[GridSearchResult] = []
        for i, params in enumerate(grid):
            try:
                metrics = self.runner.run_strategy(
                    ohlcv, config.strategy_name, params
                )
                results.append(
                    GridSearchResult(
                        parameters=params,
                        metrics=asdict(metrics),
                    )
                )
            except Exception:
                logger.warning(
                    "Backtest failed for params %s, skipping", params, exc_info=True
                )

            if (i + 1) % 50 == 0:
                logger.info("Progress: %d/%d combinations", i + 1, len(grid))

        # Rank by Sharpe ratio descending
        results.sort(
            key=lambda r: r.metrics.get("sharpe_ratio", float("-inf")),
            reverse=True,
        )

        # Assign ranks and return top N
        for rank, result in enumerate(results, start=1):
            result.rank = rank

        top_results = results[: config.top_n]
        logger.info(
            "Grid search complete: %d/%d succeeded, returning top %d",
            len(results),
            len(grid),
            len(top_results),
        )
        return top_results
