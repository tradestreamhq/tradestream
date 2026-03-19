"""A/B Testing — runs original vs adapted parameters in parallel.

Manages experiments that compare a control (original parameters) against
a treatment (adapted parameters) for each strategy. Tracks observations
and determines statistical significance of improvements.
"""

import json
import math
import uuid
from datetime import datetime, timezone

from absl import logging


class ABTestManager:
    """Manages A/B test experiments for parameter adaptations."""

    def __init__(self, db_connection=None):
        self._conn = db_connection

    def create_experiment(self, strategy_spec_id, instrument,
                           control_parameters, treatment_parameters,
                           hypothesis=None):
        """Create a new A/B test experiment.

        Args:
            strategy_spec_id: UUID of the strategy being tested.
            instrument: Trading instrument.
            control_parameters: Original strategy parameters.
            treatment_parameters: Adapted strategy parameters.
            hypothesis: Description of expected improvement.

        Returns:
            Experiment dict with ID.
        """
        experiment_id = str(uuid.uuid4())
        experiment = {
            "id": experiment_id,
            "strategy_spec_id": strategy_spec_id,
            "instrument": instrument,
            "control_parameters": control_parameters,
            "treatment_parameters": treatment_parameters,
            "hypothesis": hypothesis,
            "status": "running",
        }

        if self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ab_test_experiments (
                        id, strategy_spec_id, instrument,
                        control_parameters, treatment_parameters, hypothesis
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        experiment_id,
                        strategy_spec_id,
                        instrument,
                        json.dumps(control_parameters),
                        json.dumps(treatment_parameters),
                        hypothesis,
                    ),
                )
            self._conn.commit()

        logging.info(
            "Created A/B experiment %s for strategy %s",
            experiment_id, strategy_spec_id,
        )
        return experiment

    def record_observation(self, experiment_id, variant, pnl_percent,
                            pnl_absolute=None, signal_type=None,
                            entry_price=None, exit_price=None,
                            hold_duration=None, metadata=None):
        """Record a single observation for an experiment variant.

        Args:
            experiment_id: UUID of the experiment.
            variant: 'control' or 'treatment'.
            pnl_percent: P&L percentage for this observation.
            Additional optional fields for context.

        Returns:
            Observation ID.
        """
        obs_id = str(uuid.uuid4())

        if self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ab_test_observations (
                        id, experiment_id, variant, pnl_percent,
                        pnl_absolute, signal_type, entry_price, exit_price,
                        hold_duration, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        obs_id,
                        experiment_id,
                        variant,
                        pnl_percent,
                        pnl_absolute,
                        signal_type,
                        entry_price,
                        exit_price,
                        hold_duration,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
            self._conn.commit()

        return obs_id

    def evaluate_experiment(self, experiment_id):
        """Evaluate experiment results with statistical comparison.

        Returns:
            dict with control_metrics, treatment_metrics, improvement,
            is_significant, recommendation.
        """
        control_obs = self._get_observations(experiment_id, "control")
        treatment_obs = self._get_observations(experiment_id, "treatment")

        control_metrics = self._compute_variant_metrics(control_obs)
        treatment_metrics = self._compute_variant_metrics(treatment_obs)

        improvement = self._calculate_improvement(control_metrics, treatment_metrics)
        is_significant = self._check_significance(control_obs, treatment_obs)

        if treatment_metrics["avg_pnl"] is not None and control_metrics["avg_pnl"] is not None:
            if treatment_metrics["avg_pnl"] > control_metrics["avg_pnl"] and is_significant:
                recommendation = "adopt_treatment"
            elif treatment_metrics["avg_pnl"] < control_metrics["avg_pnl"] and is_significant:
                recommendation = "keep_control"
            else:
                recommendation = "continue_testing"
        else:
            recommendation = "insufficient_data"

        result = {
            "experiment_id": experiment_id,
            "control": control_metrics,
            "treatment": treatment_metrics,
            "improvement": improvement,
            "is_significant": is_significant,
            "recommendation": recommendation,
            "total_observations": len(control_obs) + len(treatment_obs),
        }

        logging.info(
            "Experiment %s: recommendation=%s, improvement=%.2f%%",
            experiment_id, recommendation, (improvement or 0) * 100,
        )
        return result

    def complete_experiment(self, experiment_id, recommendation=None):
        """Mark an experiment as completed."""
        if not self._conn:
            return
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ab_test_experiments
                SET status = 'completed', ended_at = NOW()
                WHERE id = %s
                """,
                (experiment_id,),
            )
        self._conn.commit()

        if self._conn and recommendation:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO adaptation_log (id, event_type, details)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        "ab_test_result",
                        json.dumps({
                            "experiment_id": experiment_id,
                            "recommendation": recommendation,
                        }),
                    ),
                )
            self._conn.commit()

    def _get_observations(self, experiment_id, variant):
        """Get all observations for a variant."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT pnl_percent, pnl_absolute, signal_type,
                       entry_price, exit_price, hold_duration, metadata
                FROM ab_test_observations
                WHERE experiment_id = %s AND variant = %s
                ORDER BY created_at
                """,
                (experiment_id, variant),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def _compute_variant_metrics(self, observations):
        """Compute aggregate metrics for a variant's observations."""
        pnls = [float(o["pnl_percent"]) for o in observations
                if o.get("pnl_percent") is not None]
        if not pnls:
            return {
                "count": 0,
                "avg_pnl": None,
                "total_pnl": None,
                "win_rate": None,
                "sharpe": None,
                "std_pnl": None,
            }

        avg_pnl = sum(pnls) / len(pnls)
        win_count = sum(1 for p in pnls if p > 0)
        win_rate = win_count / len(pnls)

        if len(pnls) >= 2:
            variance = sum((p - avg_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
            std = math.sqrt(variance)
            sharpe = (avg_pnl / std * math.sqrt(252)) if std > 0 else None
        else:
            std = None
            sharpe = None

        return {
            "count": len(pnls),
            "avg_pnl": round(avg_pnl, 4),
            "total_pnl": round(sum(pnls), 4),
            "win_rate": round(win_rate, 4),
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
            "std_pnl": round(std, 4) if std is not None else None,
        }

    def _calculate_improvement(self, control, treatment):
        """Calculate relative improvement of treatment over control."""
        if control["avg_pnl"] is None or treatment["avg_pnl"] is None:
            return None
        if control["avg_pnl"] == 0:
            return None
        return (treatment["avg_pnl"] - control["avg_pnl"]) / abs(control["avg_pnl"])

    def _check_significance(self, control_obs, treatment_obs, alpha=0.05):
        """Check statistical significance using Welch's t-test approximation.

        Returns True if the difference is statistically significant.
        """
        c_pnls = [float(o["pnl_percent"]) for o in control_obs
                   if o.get("pnl_percent") is not None]
        t_pnls = [float(o["pnl_percent"]) for o in treatment_obs
                   if o.get("pnl_percent") is not None]

        if len(c_pnls) < 5 or len(t_pnls) < 5:
            return False

        c_mean = sum(c_pnls) / len(c_pnls)
        t_mean = sum(t_pnls) / len(t_pnls)
        c_var = sum((p - c_mean) ** 2 for p in c_pnls) / (len(c_pnls) - 1)
        t_var = sum((p - t_mean) ** 2 for p in t_pnls) / (len(t_pnls) - 1)

        se = math.sqrt(c_var / len(c_pnls) + t_var / len(t_pnls))
        if se == 0:
            return False

        t_stat = abs(t_mean - c_mean) / se

        # Approximate: for alpha=0.05 two-tailed, critical t ~ 1.96 for large n
        # Use 2.0 as conservative threshold for moderate sample sizes
        return t_stat > 2.0

    def get_running_experiments(self, strategy_spec_id=None, instrument=None):
        """Get currently running experiments."""
        if not self._conn:
            return []
        conditions = ["status = 'running'"]
        params = []
        if strategy_spec_id:
            conditions.append("strategy_spec_id = %s")
            params.append(strategy_spec_id)
        if instrument:
            conditions.append("instrument = %s")
            params.append(instrument)
        where = " AND ".join(conditions)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, strategy_spec_id, instrument,
                       control_parameters, treatment_parameters,
                       hypothesis, started_at
                FROM ab_test_experiments
                WHERE {where}
                ORDER BY started_at DESC
                """,
                tuple(params),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
