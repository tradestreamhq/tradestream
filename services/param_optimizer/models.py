"""Data models for the parameter optimizer."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Union

from services.backtesting.vectorbt_runner import BacktestMetrics


@dataclass
class ParameterRange:
    """Defines the search space for a single parameter.

    Attributes:
        name: Parameter name (must match the strategy's expected key).
        values: Explicit list of values to search over.
    """

    name: str
    values: List[Union[int, float]]

    def __post_init__(self):
        if not self.values:
            raise ValueError(f"Parameter '{self.name}' must have at least one value")


@dataclass
class ParameterSetResult:
    """Result of backtesting a single parameter combination.

    Attributes:
        parameters: The parameter dict used for this backtest.
        metrics: Full backtest metrics for this run.
    """

    parameters: Dict[str, Any]
    metrics: BacktestMetrics


@dataclass
class OptimizationResult:
    """Complete result of a grid search optimization.

    Attributes:
        strategy_name: Name of the strategy optimized.
        total_combinations: Total parameter combos evaluated.
        top_results: Best parameter sets ranked by objective.
        all_results: Every evaluated combination (if retained).
        max_drawdown_limit: Drawdown constraint applied.
    """

    strategy_name: str
    total_combinations: int
    top_results: List[ParameterSetResult]
    all_results: List[ParameterSetResult] = field(default_factory=list)
    max_drawdown_limit: float = 1.0
