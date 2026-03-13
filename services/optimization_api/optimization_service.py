"""
Strategy Parameter Optimization Service.

Runs grid search or random search over strategy hyperparameters,
evaluating each combination via backtesting and ranking by objective metric.
"""

import itertools
import logging
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class SearchMethod(str, Enum):
    GRID = "grid"
    RANDOM = "random"


class Objective(str, Enum):
    SHARPE = "sharpe"
    RETURN = "return"
    DRAWDOWN = "drawdown"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class NumericParamSpace:
    """Defines a numeric parameter range: [min, max] with step."""

    name: str
    min: float
    max: float
    step: float


@dataclass
class CategoricalParamSpace:
    """Defines a categorical parameter with explicit options."""

    name: str
    options: List[Any]


@dataclass
class TrialResult:
    """Result of a single parameter combination trial."""

    parameters: Dict[str, Any]
    objective_value: float
    sharpe_ratio: float
    cumulative_return: float
    max_drawdown: float
    number_of_trades: int
    win_rate: float
    profit_factor: float
    sortino_ratio: float
    strategy_score: float


@dataclass
class OptimizationResult:
    """Full optimization job result."""

    job_id: str
    strategy_id: str
    status: JobStatus
    search_method: SearchMethod
    objective: Objective
    total_combinations: int
    completed_combinations: int
    best_parameters: Optional[Dict[str, Any]] = None
    best_objective_value: Optional[float] = None
    ranked_results: List[TrialResult] = field(default_factory=list)
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


def generate_param_grid(
    numeric_params: List[NumericParamSpace],
    categorical_params: List[CategoricalParamSpace],
) -> List[Dict[str, Any]]:
    """Generate all parameter combinations from the given spaces.

    For numeric params, produces values from min to max (inclusive) by step.
    For categorical params, uses the provided options list.

    Returns:
        List of dicts, each mapping param name to a specific value.
    """
    all_values: Dict[str, List[Any]] = {}

    for p in numeric_params:
        values = []
        v = p.min
        while v <= p.max + 1e-9:  # tolerance for float rounding
            values.append(round(v, 10))
            v += p.step
        all_values[p.name] = values

    for p in categorical_params:
        all_values[p.name] = list(p.options)

    if not all_values:
        return [{}]

    names = list(all_values.keys())
    combos = list(itertools.product(*(all_values[n] for n in names)))
    return [dict(zip(names, combo)) for combo in combos]


def sample_random_params(
    numeric_params: List[NumericParamSpace],
    categorical_params: List[CategoricalParamSpace],
    n_samples: int,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Sample random parameter combinations.

    Numeric params are sampled uniformly within [min, max] and snapped to the
    nearest step boundary. Categorical params are sampled uniformly.

    Returns:
        List of n_samples parameter dicts.
    """
    rng = random.Random(seed)
    results: List[Dict[str, Any]] = []

    for _ in range(n_samples):
        combo: Dict[str, Any] = {}
        for p in numeric_params:
            num_steps = int(round((p.max - p.min) / p.step))
            step_idx = rng.randint(0, num_steps)
            combo[p.name] = round(p.min + step_idx * p.step, 10)
        for p in categorical_params:
            combo[p.name] = rng.choice(p.options)
        results.append(combo)

    return results


def get_objective_value(trial: TrialResult, objective: Objective) -> float:
    """Extract the objective metric from a trial result."""
    if objective == Objective.SHARPE:
        return trial.sharpe_ratio
    elif objective == Objective.RETURN:
        return trial.cumulative_return
    elif objective == Objective.DRAWDOWN:
        # Lower drawdown is better, so negate for ranking (higher = better)
        return -trial.max_drawdown
    raise ValueError(f"Unknown objective: {objective}")


def rank_results(
    trials: List[TrialResult], objective: Objective
) -> List[TrialResult]:
    """Rank trial results by the given objective (best first)."""
    return sorted(trials, key=lambda t: get_objective_value(t, objective), reverse=True)
