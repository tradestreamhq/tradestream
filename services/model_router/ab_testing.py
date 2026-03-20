"""A/B Model Testing — compare model outputs for the same task to optimize routing.

Allows running experiments where a percentage of requests are sent to both the
primary and a challenger model. Results are collected for offline comparison of
quality, latency, and cost.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Single result from an A/B experiment run."""

    experiment_id: str
    agent_type: str
    primary_model: str
    challenger_model: str
    primary_latency_ms: float
    challenger_latency_ms: float
    primary_tokens: int
    challenger_tokens: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class Experiment:
    """An active A/B experiment comparing two models."""

    experiment_id: str
    agent_type: str
    primary_model: str
    challenger_model: str
    traffic_pct: float  # 0.0–1.0, fraction sent to both models
    max_runs: int = 100
    results: list[ExperimentResult] = field(default_factory=list)
    active: bool = True

    @property
    def runs(self) -> int:
        return len(self.results)

    @property
    def complete(self) -> bool:
        return self.runs >= self.max_runs

    def should_shadow(self) -> bool:
        """Decide whether this request should also run on the challenger."""
        if not self.active or self.complete:
            return False
        return random.random() < self.traffic_pct

    def record(self, result: ExperimentResult):
        self.results.append(result)
        if self.complete:
            self.active = False
            logger.info(
                "Experiment %s complete after %d runs",
                self.experiment_id,
                self.runs,
            )

    def summary(self) -> dict:
        if not self.results:
            return {
                "experiment_id": self.experiment_id,
                "runs": 0,
                "active": self.active,
            }
        primary_latencies = [r.primary_latency_ms for r in self.results]
        challenger_latencies = [r.challenger_latency_ms for r in self.results]
        primary_tokens = [r.primary_tokens for r in self.results]
        challenger_tokens = [r.challenger_tokens for r in self.results]
        return {
            "experiment_id": self.experiment_id,
            "agent_type": self.agent_type,
            "primary_model": self.primary_model,
            "challenger_model": self.challenger_model,
            "runs": self.runs,
            "max_runs": self.max_runs,
            "active": self.active,
            "primary_avg_latency_ms": sum(primary_latencies) / len(primary_latencies),
            "challenger_avg_latency_ms": (
                sum(challenger_latencies) / len(challenger_latencies)
            ),
            "primary_avg_tokens": sum(primary_tokens) / len(primary_tokens),
            "challenger_avg_tokens": sum(challenger_tokens) / len(challenger_tokens),
        }


class ABTestManager:
    """Manages A/B experiments across agent types."""

    def __init__(self):
        self._experiments: dict[str, Experiment] = {}

    def create_experiment(
        self,
        experiment_id: str,
        agent_type: str,
        primary_model: str,
        challenger_model: str,
        traffic_pct: float = 0.1,
        max_runs: int = 100,
    ) -> Experiment:
        if experiment_id in self._experiments:
            raise ValueError(f"Experiment {experiment_id} already exists")
        if not 0.0 < traffic_pct <= 1.0:
            raise ValueError("traffic_pct must be between 0 and 1")
        exp = Experiment(
            experiment_id=experiment_id,
            agent_type=agent_type,
            primary_model=primary_model,
            challenger_model=challenger_model,
            traffic_pct=traffic_pct,
            max_runs=max_runs,
        )
        self._experiments[experiment_id] = exp
        logger.info(
            "Created experiment %s: %s vs %s for %s (%.0f%% traffic)",
            experiment_id,
            primary_model,
            challenger_model,
            agent_type,
            traffic_pct * 100,
        )
        return exp

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        return self._experiments.get(experiment_id)

    def get_active_for_agent(self, agent_type: str) -> Optional[Experiment]:
        """Get the active experiment for an agent type, if any."""
        for exp in self._experiments.values():
            if exp.agent_type == agent_type and exp.active:
                return exp
        return None

    def stop_experiment(self, experiment_id: str) -> bool:
        exp = self._experiments.get(experiment_id)
        if not exp:
            return False
        exp.active = False
        return True

    def list_experiments(self) -> list[dict]:
        return [exp.summary() for exp in self._experiments.values()]

    def record_result(
        self,
        experiment_id: str,
        agent_type: str,
        primary_model: str,
        challenger_model: str,
        primary_latency_ms: float,
        challenger_latency_ms: float,
        primary_tokens: int,
        challenger_tokens: int,
    ) -> Optional[ExperimentResult]:
        exp = self._experiments.get(experiment_id)
        if not exp or not exp.active:
            return None
        result = ExperimentResult(
            experiment_id=experiment_id,
            agent_type=agent_type,
            primary_model=primary_model,
            challenger_model=challenger_model,
            primary_latency_ms=primary_latency_ms,
            challenger_latency_ms=challenger_latency_ms,
            primary_tokens=primary_tokens,
            challenger_tokens=challenger_tokens,
        )
        exp.record(result)
        return result
