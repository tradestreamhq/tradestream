"""
Strategy Parameter Optimization Service.

Provides grid search and random search over strategy parameters
to find optimal configurations using the backtesting framework.
"""

import itertools
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner
from services.backtesting.yaml_strategy_loader import YamlStrategyLoader

logger = logging.getLogger(__name__)


@dataclass
class ParameterSpace:
    """Defines the search space for a single parameter."""

    name: str
    param_type: str  # "INTEGER" or "DOUBLE"
    min_value: float
    max_value: float
    step: Optional[float] = None

    @property
    def grid_values(self) -> List[float]:
        """Generate all grid values for this parameter."""
        if self.step is None:
            step = (
                1
                if self.param_type == "INTEGER"
                else (self.max_value - self.min_value) / 10
            )
        else:
            step = self.step

        values = []
        v = self.min_value
        while v <= self.max_value + 1e-9:
            values.append(int(v) if self.param_type == "INTEGER" else round(v, 6))
            v += step
        return values

    @property
    def grid_size(self) -> int:
        return len(self.grid_values)

    def sample(self) -> float:
        """Sample a random value from this parameter space."""
        if self.param_type == "INTEGER":
            return random.randint(int(self.min_value), int(self.max_value))
        return random.uniform(self.min_value, self.max_value)


@dataclass
class OptimizationResult:
    """Result of a single parameter evaluation."""

    parameters: Dict[str, Any]
    metrics: BacktestMetrics
    rank: int = 0


@dataclass
class WalkForwardWindow:
    """A single train/test window for walk-forward validation."""

    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass
class WalkForwardResult:
    """Result of walk-forward validation for a parameter set."""

    parameters: Dict[str, Any]
    train_metrics: List[BacktestMetrics]
    test_metrics: List[BacktestMetrics]
    mean_train_sharpe: float = 0.0
    mean_test_sharpe: float = 0.0
    overfitting_ratio: float = 0.0


class ParameterOptimizer:
    """
    Optimizes strategy parameters using grid search or random search.

    Supports both hardcoded strategies (via VectorBTRunner) and
    YAML-defined strategies (via YamlStrategyLoader).
    """

    METRIC_ACCESSORS = {
        "sharpe_ratio": lambda m: m.sharpe_ratio,
        "sortino_ratio": lambda m: m.sortino_ratio,
        "cumulative_return": lambda m: m.cumulative_return,
        "annualized_return": lambda m: m.annualized_return,
        "profit_factor": lambda m: m.profit_factor,
        "win_rate": lambda m: m.win_rate,
        "strategy_score": lambda m: m.strategy_score,
        "max_drawdown": lambda m: -m.max_drawdown,  # negate so higher = better
    }

    def __init__(
        self,
        runner: Optional[VectorBTRunner] = None,
        yaml_loader: Optional[YamlStrategyLoader] = None,
    ):
        self.runner = runner or VectorBTRunner()
        self.yaml_loader = yaml_loader or YamlStrategyLoader()

    @staticmethod
    def spaces_from_yaml(strategy_spec: Dict[str, Any]) -> List[ParameterSpace]:
        """Extract parameter search spaces from a YAML strategy spec."""
        spaces = []
        for param_def in strategy_spec.get("parameters", []):
            if "min" in param_def and "max" in param_def:
                spaces.append(
                    ParameterSpace(
                        name=param_def["name"],
                        param_type=param_def.get("type", "DOUBLE"),
                        min_value=float(param_def["min"]),
                        max_value=float(param_def["max"]),
                        step=float(param_def["step"]) if "step" in param_def else None,
                    )
                )
        return spaces

    @staticmethod
    def total_grid_size(spaces: List[ParameterSpace]) -> int:
        """Calculate total number of combinations for grid search."""
        if not spaces:
            return 0
        size = 1
        for s in spaces:
            size *= s.grid_size
        return size

    def grid_search(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        param_spaces: List[ParameterSpace],
        metric: str = "sharpe_ratio",
        top_n: int = 10,
        strategy_spec: Optional[Dict[str, Any]] = None,
    ) -> List[OptimizationResult]:
        """
        Exhaustive grid search over all parameter combinations.

        Args:
            ohlcv: OHLCV price data
            strategy_name: Strategy name for hardcoded strategies
            param_spaces: Parameter search spaces
            metric: Metric to optimize (default: sharpe_ratio)
            top_n: Number of top results to return
            strategy_spec: Optional YAML strategy spec for YAML-based strategies

        Returns:
            Top N parameter sets ranked by the chosen metric
        """
        if metric not in self.METRIC_ACCESSORS:
            raise ValueError(
                f"Unknown metric: {metric}. Choose from: {list(self.METRIC_ACCESSORS.keys())}"
            )

        all_values = [s.grid_values for s in param_spaces]
        param_names = [s.name for s in param_spaces]
        total = self.total_grid_size(param_spaces)

        logger.info(
            "Grid search: %d combinations for strategy %s", total, strategy_name
        )

        results = []
        for i, combo in enumerate(itertools.product(*all_values)):
            params = dict(zip(param_names, combo))
            metrics = self._run_single(ohlcv, strategy_name, params, strategy_spec)
            results.append(OptimizationResult(parameters=params, metrics=metrics))

            if (i + 1) % 100 == 0:
                logger.info("Grid search progress: %d/%d", i + 1, total)

        return self._rank_results(results, metric, top_n)

    def random_search(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        param_spaces: List[ParameterSpace],
        n_iterations: int = 100,
        metric: str = "sharpe_ratio",
        top_n: int = 10,
        seed: Optional[int] = None,
        strategy_spec: Optional[Dict[str, Any]] = None,
    ) -> List[OptimizationResult]:
        """
        Random search over parameter space.

        Args:
            ohlcv: OHLCV price data
            strategy_name: Strategy name
            param_spaces: Parameter search spaces
            n_iterations: Number of random samples to evaluate
            metric: Metric to optimize
            top_n: Number of top results to return
            seed: Random seed for reproducibility
            strategy_spec: Optional YAML strategy spec

        Returns:
            Top N parameter sets ranked by the chosen metric
        """
        if metric not in self.METRIC_ACCESSORS:
            raise ValueError(
                f"Unknown metric: {metric}. Choose from: {list(self.METRIC_ACCESSORS.keys())}"
            )

        if seed is not None:
            random.seed(seed)

        logger.info(
            "Random search: %d iterations for strategy %s",
            n_iterations,
            strategy_name,
        )

        results = []
        for i in range(n_iterations):
            params = {s.name: s.sample() for s in param_spaces}
            metrics = self._run_single(ohlcv, strategy_name, params, strategy_spec)
            results.append(OptimizationResult(parameters=params, metrics=metrics))

            if (i + 1) % 100 == 0:
                logger.info("Random search progress: %d/%d", i + 1, n_iterations)

        return self._rank_results(results, metric, top_n)

    def walk_forward_validate(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        param_spaces: List[ParameterSpace],
        train_bars: int,
        test_bars: int,
        step_bars: Optional[int] = None,
        search_method: str = "random",
        n_iterations: int = 50,
        metric: str = "sharpe_ratio",
        strategy_spec: Optional[Dict[str, Any]] = None,
    ) -> List[WalkForwardResult]:
        """
        Walk-forward validation: optimize on training windows, validate on test windows.

        Args:
            ohlcv: Full OHLCV dataset
            strategy_name: Strategy name
            param_spaces: Parameter search spaces
            train_bars: Number of bars in each training window
            test_bars: Number of bars in each test window
            step_bars: Step size between windows (defaults to test_bars)
            search_method: "grid" or "random"
            n_iterations: Iterations for random search
            metric: Optimization metric
            strategy_spec: Optional YAML strategy spec

        Returns:
            Walk-forward results for the best parameter set from each window
        """
        if step_bars is None:
            step_bars = test_bars

        windows = self._create_windows(len(ohlcv), train_bars, test_bars, step_bars)
        if not windows:
            raise ValueError(
                f"Not enough data for walk-forward: need at least {train_bars + test_bars} bars, "
                f"got {len(ohlcv)}"
            )

        logger.info(
            "Walk-forward validation: %d windows, train=%d, test=%d",
            len(windows),
            train_bars,
            test_bars,
        )

        # For each window, optimize on train, evaluate on test
        wf_results: Dict[str, WalkForwardResult] = {}

        for wi, window in enumerate(windows):
            train_data = ohlcv.iloc[window.train_start : window.train_end]
            test_data = ohlcv.iloc[window.test_start : window.test_end]

            # Optimize on training data
            if search_method == "grid":
                train_results = self.grid_search(
                    train_data,
                    strategy_name,
                    param_spaces,
                    metric=metric,
                    top_n=1,
                    strategy_spec=strategy_spec,
                )
            else:
                train_results = self.random_search(
                    train_data,
                    strategy_name,
                    param_spaces,
                    n_iterations=n_iterations,
                    metric=metric,
                    top_n=1,
                    strategy_spec=strategy_spec,
                )

            if not train_results:
                continue

            best = train_results[0]
            params_key = str(sorted(best.parameters.items()))

            # Evaluate best params on test data
            test_metrics = self._run_single(
                test_data, strategy_name, best.parameters, strategy_spec
            )

            if params_key not in wf_results:
                wf_results[params_key] = WalkForwardResult(
                    parameters=best.parameters,
                    train_metrics=[],
                    test_metrics=[],
                )

            wf_results[params_key].train_metrics.append(best.metrics)
            wf_results[params_key].test_metrics.append(test_metrics)

        # Compute summary statistics
        accessor = self.METRIC_ACCESSORS[metric]
        results = []
        for wfr in wf_results.values():
            if wfr.train_metrics and wfr.test_metrics:
                wfr.mean_train_sharpe = float(
                    np.mean([accessor(m) for m in wfr.train_metrics])
                )
                wfr.mean_test_sharpe = float(
                    np.mean([accessor(m) for m in wfr.test_metrics])
                )
                if wfr.mean_train_sharpe != 0:
                    wfr.overfitting_ratio = 1 - (
                        wfr.mean_test_sharpe / wfr.mean_train_sharpe
                    )
                results.append(wfr)

        # Sort by test performance
        results.sort(key=lambda r: r.mean_test_sharpe, reverse=True)
        return results

    def _run_single(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        params: Dict[str, Any],
        strategy_spec: Optional[Dict[str, Any]],
    ) -> BacktestMetrics:
        """Run a single backtest with given parameters."""
        if strategy_spec is not None:
            entry, exit_ = self.yaml_loader.generate_signals(
                ohlcv, strategy_spec, parameter_overrides=params
            )
            return self.runner.run_backtest(ohlcv, entry, exit_)
        return self.runner.run_strategy(ohlcv, strategy_name, params)

    @staticmethod
    def _create_windows(
        total_bars: int,
        train_bars: int,
        test_bars: int,
        step_bars: int,
    ) -> List[WalkForwardWindow]:
        """Create rolling train/test windows."""
        windows = []
        start = 0
        while start + train_bars + test_bars <= total_bars:
            windows.append(
                WalkForwardWindow(
                    train_start=start,
                    train_end=start + train_bars,
                    test_start=start + train_bars,
                    test_end=start + train_bars + test_bars,
                )
            )
            start += step_bars
        return windows

    def _rank_results(
        self,
        results: List[OptimizationResult],
        metric: str,
        top_n: int,
    ) -> List[OptimizationResult]:
        """Rank results by the chosen metric and return top N."""
        accessor = self.METRIC_ACCESSORS[metric]
        results.sort(key=lambda r: accessor(r.metrics), reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1
        return results[:top_n]
