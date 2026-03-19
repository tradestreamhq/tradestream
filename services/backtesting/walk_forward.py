"""
Walk-Forward Optimization.

Splits historical data into rolling train/test windows, runs backtests on each,
and evaluates whether in-sample performance degrades out-of-sample (overfitting detection).
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward optimization."""

    train_window_bars: int = 6480  # 9 months @ 1min
    test_window_bars: int = 2160  # 3 months @ 1min
    step_bars: int = 2160  # 3 months step
    min_windows: int = 4


@dataclass
class WindowResult:
    """Result from a single walk-forward window."""

    window_index: int
    in_sample_result: BacktestMetrics
    out_of_sample_result: BacktestMetrics
    train_start_bar: int
    train_end_bar: int
    test_start_bar: int
    test_end_bar: int


@dataclass
class WalkForwardResult:
    """Full walk-forward validation result."""

    status: str  # APPROVED, REJECTED, INSUFFICIENT_DATA
    rejection_reason: str
    windows_count: int
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    sharpe_degradation: float
    oos_sharpe_std_dev: float
    window_results: List[WindowResult]
    in_sample_return: float
    out_of_sample_return: float
    return_degradation: float


class WalkForwardOptimizer:
    """Walk-forward optimization engine."""

    # Thresholds for validation
    MAX_SHARPE_DEGRADATION = 0.5  # Reject if OOS Sharpe < 50% of IS Sharpe
    MAX_OOS_SHARPE_STD = 1.5  # Reject if OOS Sharpe too inconsistent
    MIN_OOS_SHARPE = -0.5  # Reject if average OOS Sharpe is very negative

    def __init__(self, runner: Optional[VectorBTRunner] = None):
        self.runner = runner or VectorBTRunner()

    def run(
        self,
        ohlcv: pd.DataFrame,
        strategy_name: str,
        parameters: dict,
        config: Optional[WalkForwardConfig] = None,
    ) -> WalkForwardResult:
        """Run walk-forward validation on a strategy.

        Splits data into rolling train/test windows, backtests each,
        and compares in-sample vs out-of-sample performance.
        """
        config = config or WalkForwardConfig()
        total_bars = len(ohlcv)
        min_required = config.train_window_bars + config.test_window_bars

        if total_bars < min_required:
            return WalkForwardResult(
                status="INSUFFICIENT_DATA",
                rejection_reason=(
                    f"Need at least {min_required} bars, got {total_bars}"
                ),
                windows_count=0,
                in_sample_sharpe=0.0,
                out_of_sample_sharpe=0.0,
                sharpe_degradation=0.0,
                oos_sharpe_std_dev=0.0,
                window_results=[],
                in_sample_return=0.0,
                out_of_sample_return=0.0,
                return_degradation=0.0,
            )

        windows = self._generate_windows(total_bars, config)

        if len(windows) < config.min_windows:
            return WalkForwardResult(
                status="INSUFFICIENT_DATA",
                rejection_reason=(
                    f"Only {len(windows)} windows available, "
                    f"need at least {config.min_windows}"
                ),
                windows_count=len(windows),
                in_sample_sharpe=0.0,
                out_of_sample_sharpe=0.0,
                sharpe_degradation=0.0,
                oos_sharpe_std_dev=0.0,
                window_results=[],
                in_sample_return=0.0,
                out_of_sample_return=0.0,
                return_degradation=0.0,
            )

        window_results = []
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            train_data = ohlcv.iloc[train_start:train_end].reset_index(drop=True)
            test_data = ohlcv.iloc[test_start:test_end].reset_index(drop=True)

            # Re-index for VectorBT
            train_data.index = pd.date_range(
                start="2020-01-01", periods=len(train_data), freq="1min"
            )
            test_data.index = pd.date_range(
                start="2020-01-01", periods=len(test_data), freq="1min"
            )

            is_result = self.runner.run_strategy(
                train_data, strategy_name, parameters
            )
            oos_result = self.runner.run_strategy(
                test_data, strategy_name, parameters
            )

            window_results.append(
                WindowResult(
                    window_index=i,
                    in_sample_result=is_result,
                    out_of_sample_result=oos_result,
                    train_start_bar=train_start,
                    train_end_bar=train_end,
                    test_start_bar=test_start,
                    test_end_bar=test_end,
                )
            )

        return self._evaluate(window_results)

    def _generate_windows(
        self, total_bars: int, config: WalkForwardConfig
    ) -> List[Tuple[int, int, int, int]]:
        """Generate (train_start, train_end, test_start, test_end) tuples."""
        windows = []
        start = 0
        while True:
            train_start = start
            train_end = train_start + config.train_window_bars
            test_start = train_end
            test_end = test_start + config.test_window_bars

            if test_end > total_bars:
                break

            windows.append((train_start, train_end, test_start, test_end))
            start += config.step_bars

        return windows

    def _evaluate(self, window_results: List[WindowResult]) -> WalkForwardResult:
        """Evaluate walk-forward results and determine validation status."""
        is_sharpes = [w.in_sample_result.sharpe_ratio for w in window_results]
        oos_sharpes = [w.out_of_sample_result.sharpe_ratio for w in window_results]
        is_returns = [w.in_sample_result.cumulative_return for w in window_results]
        oos_returns = [w.out_of_sample_result.cumulative_return for w in window_results]

        avg_is_sharpe = float(np.mean(is_sharpes))
        avg_oos_sharpe = float(np.mean(oos_sharpes))
        oos_sharpe_std = float(np.std(oos_sharpes))
        avg_is_return = float(np.mean(is_returns))
        avg_oos_return = float(np.mean(oos_returns))

        # Sharpe degradation: 1 - (OOS / IS)
        if abs(avg_is_sharpe) > 1e-9:
            sharpe_degradation = 1.0 - (avg_oos_sharpe / avg_is_sharpe)
        else:
            sharpe_degradation = 0.0

        # Return degradation
        if abs(avg_is_return) > 1e-9:
            return_degradation = 1.0 - (avg_oos_return / avg_is_return)
        else:
            return_degradation = 0.0

        # Determine status
        status = "APPROVED"
        rejection_reason = ""

        if avg_oos_sharpe < self.MIN_OOS_SHARPE:
            status = "REJECTED"
            rejection_reason = (
                f"Average OOS Sharpe ({avg_oos_sharpe:.3f}) "
                f"below minimum ({self.MIN_OOS_SHARPE})"
            )
        elif sharpe_degradation > self.MAX_SHARPE_DEGRADATION:
            status = "REJECTED"
            rejection_reason = (
                f"Sharpe degradation ({sharpe_degradation:.1%}) "
                f"exceeds threshold ({self.MAX_SHARPE_DEGRADATION:.0%}), "
                f"likely overfit"
            )
        elif oos_sharpe_std > self.MAX_OOS_SHARPE_STD:
            status = "REJECTED"
            rejection_reason = (
                f"OOS Sharpe std dev ({oos_sharpe_std:.3f}) "
                f"exceeds threshold ({self.MAX_OOS_SHARPE_STD}), "
                f"inconsistent performance"
            )

        return WalkForwardResult(
            status=status,
            rejection_reason=rejection_reason,
            windows_count=len(window_results),
            in_sample_sharpe=avg_is_sharpe,
            out_of_sample_sharpe=avg_oos_sharpe,
            sharpe_degradation=sharpe_degradation,
            oos_sharpe_std_dev=oos_sharpe_std,
            window_results=window_results,
            in_sample_return=avg_is_return,
            out_of_sample_return=avg_oos_return,
            return_degradation=return_degradation,
        )
