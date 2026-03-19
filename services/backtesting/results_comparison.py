"""
Results Comparison: VectorBT vs Ta4j.

Compares backtest results from both engines to validate
that VectorBT produces consistent metrics.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from services.backtesting.vectorbt_runner import BacktestMetrics

logger = logging.getLogger(__name__)


@dataclass
class MetricComparison:
    """Comparison of a single metric between two engines."""

    metric_name: str
    vectorbt_value: float
    ta4j_value: float
    absolute_diff: float
    relative_diff: float  # percentage
    within_tolerance: bool


@dataclass
class ComparisonResult:
    """Full comparison between VectorBT and Ta4j results."""

    strategy_name: str
    vectorbt_result: BacktestMetrics
    ta4j_result: BacktestMetrics
    metric_comparisons: Dict[str, MetricComparison]
    overall_match: bool
    match_ratio: float  # fraction of metrics within tolerance
    summary: str


class ResultsComparator:
    """Compares VectorBT and Ta4j backtest results for validation."""

    # Default tolerance: metrics must be within these bounds to match
    DEFAULT_TOLERANCES = {
        "cumulative_return": 0.05,  # 5% relative tolerance
        "annualized_return": 0.10,
        "sharpe_ratio": 0.15,
        "sortino_ratio": 0.20,
        "max_drawdown": 0.10,
        "volatility": 0.10,
        "win_rate": 0.05,
        "profit_factor": 0.15,
        "number_of_trades": 0.10,
        "average_trade_duration": 0.20,
        "alpha": 0.25,
        "beta": 0.25,
        "strategy_score": 0.15,
    }

    # Minimum required match ratio to consider overall match
    MIN_MATCH_RATIO = 0.70

    def __init__(
        self, tolerances: Optional[Dict[str, float]] = None
    ):
        self.tolerances = tolerances or self.DEFAULT_TOLERANCES

    def compare(
        self,
        strategy_name: str,
        vectorbt_result: BacktestMetrics,
        ta4j_result: BacktestMetrics,
    ) -> ComparisonResult:
        """Compare VectorBT and Ta4j results for a strategy."""
        comparisons = {}
        metrics_to_compare = [
            ("cumulative_return", vectorbt_result.cumulative_return, ta4j_result.cumulative_return),
            ("annualized_return", vectorbt_result.annualized_return, ta4j_result.annualized_return),
            ("sharpe_ratio", vectorbt_result.sharpe_ratio, ta4j_result.sharpe_ratio),
            ("sortino_ratio", vectorbt_result.sortino_ratio, ta4j_result.sortino_ratio),
            ("max_drawdown", vectorbt_result.max_drawdown, ta4j_result.max_drawdown),
            ("volatility", vectorbt_result.volatility, ta4j_result.volatility),
            ("win_rate", vectorbt_result.win_rate, ta4j_result.win_rate),
            ("profit_factor", vectorbt_result.profit_factor, ta4j_result.profit_factor),
            ("number_of_trades", float(vectorbt_result.number_of_trades), float(ta4j_result.number_of_trades)),
            ("average_trade_duration", vectorbt_result.average_trade_duration, ta4j_result.average_trade_duration),
            ("alpha", vectorbt_result.alpha, ta4j_result.alpha),
            ("beta", vectorbt_result.beta, ta4j_result.beta),
            ("strategy_score", vectorbt_result.strategy_score, ta4j_result.strategy_score),
        ]

        for name, vbt_val, ta4j_val in metrics_to_compare:
            abs_diff = abs(vbt_val - ta4j_val)
            # Relative diff: use max(|a|, |b|, 1e-9) as denominator
            denom = max(abs(vbt_val), abs(ta4j_val), 1e-9)
            rel_diff = abs_diff / denom
            tolerance = self.tolerances.get(name, 0.15)

            comparisons[name] = MetricComparison(
                metric_name=name,
                vectorbt_value=vbt_val,
                ta4j_value=ta4j_val,
                absolute_diff=abs_diff,
                relative_diff=rel_diff,
                within_tolerance=rel_diff <= tolerance,
            )

        matching = sum(1 for c in comparisons.values() if c.within_tolerance)
        match_ratio = matching / len(comparisons) if comparisons else 0.0
        overall_match = match_ratio >= self.MIN_MATCH_RATIO

        mismatches = [
            c.metric_name for c in comparisons.values() if not c.within_tolerance
        ]
        if overall_match:
            summary = (
                f"MATCH: {matching}/{len(comparisons)} metrics within tolerance "
                f"({match_ratio:.0%})"
            )
        else:
            summary = (
                f"MISMATCH: {matching}/{len(comparisons)} metrics within tolerance "
                f"({match_ratio:.0%}). Mismatched: {', '.join(mismatches)}"
            )

        return ComparisonResult(
            strategy_name=strategy_name,
            vectorbt_result=vectorbt_result,
            ta4j_result=ta4j_result,
            metric_comparisons=comparisons,
            overall_match=overall_match,
            match_ratio=match_ratio,
            summary=summary,
        )

    def compare_batch(
        self,
        results: Dict[str, tuple],
    ) -> Dict[str, ComparisonResult]:
        """Compare multiple strategies.

        Args:
            results: Dict of strategy_name -> (vectorbt_result, ta4j_result)
        """
        return {
            name: self.compare(name, vbt_r, ta4j_r)
            for name, (vbt_r, ta4j_r) in results.items()
        }
