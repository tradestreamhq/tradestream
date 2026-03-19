"""Strategy Weight Optimizer — dynamically adjusts strategy allocations.

Increases allocation to strategies performing well in the current regime
and decreases allocation to underperformers. Uses a momentum-based approach
with smoothing to avoid whipsawing.
"""

import json
import uuid
from datetime import datetime, timezone

from absl import logging


# Default optimizer configuration.
DEFAULT_CONFIG = {
    "min_weight": 0.05,          # Minimum strategy weight (never fully zero out)
    "max_weight": 3.0,           # Maximum weight multiplier
    "smoothing_factor": 0.3,     # How fast weights adjust (0=no change, 1=instant)
    "sharpe_weight": 0.4,        # Importance of Sharpe ratio in scoring
    "win_rate_weight": 0.3,      # Importance of win rate
    "pnl_weight": 0.3,           # Importance of average PnL
    "min_trades_required": 5,    # Minimum trades before adjusting weight
    "default_weight": 1.0,       # Starting weight for new strategies
}


class WeightOptimizer:
    """Optimizes strategy weights based on regime-specific performance."""

    def __init__(self, db_connection=None, config=None):
        self._conn = db_connection
        self._config = config or DEFAULT_CONFIG

    def optimize_weights(self, strategy_performances, regime_type, instrument):
        """Calculate optimal weights for all strategies in the current regime.

        Args:
            strategy_performances: List of dicts with strategy_spec_id plus
                performance metrics (sharpe_ratio, win_rate, avg_pnl_percent,
                trade_count).
            regime_type: Current market regime.
            instrument: Trading instrument.

        Returns:
            List of dicts with strategy_spec_id, weight, and reason.
        """
        if not strategy_performances:
            return []

        # Score each strategy
        scored = []
        for perf in strategy_performances:
            if perf.get("trade_count", 0) < self._config["min_trades_required"]:
                scored.append({
                    "strategy_spec_id": perf["strategy_spec_id"],
                    "score": 0.0,
                    "has_data": False,
                })
                continue

            score = self._score_strategy(perf)
            scored.append({
                "strategy_spec_id": perf["strategy_spec_id"],
                "score": score,
                "has_data": True,
                "metrics": perf,
            })

        # Normalize scores to weights
        weights = self._normalize_to_weights(scored)

        # Apply smoothing against current weights
        if self._conn:
            weights = self._apply_smoothing(weights, regime_type, instrument)

        # Store new weights
        results = []
        for w in weights:
            result = {
                "strategy_spec_id": w["strategy_spec_id"],
                "weight": w["weight"],
                "previous_weight": w.get("previous_weight"),
                "reason": w.get("reason", "performance-based optimization"),
                "regime_type": regime_type,
                "instrument": instrument,
            }
            results.append(result)
            if self._conn:
                self._store_weight(result)

        logging.info(
            "Optimized weights for %d strategies in %s regime for %s",
            len(results), regime_type, instrument,
        )
        return results

    def _score_strategy(self, perf):
        """Score a strategy based on its performance metrics."""
        sharpe = float(perf.get("sharpe_ratio") or 0)
        win_rate = float(perf.get("win_rate") or 0)
        avg_pnl = float(perf.get("avg_pnl_percent") or 0)

        # Normalize components to [0, 1] range
        # Sharpe: typical range -2 to 3, map to 0-1
        sharpe_norm = max(0, min(1, (sharpe + 2) / 5))
        # Win rate already 0-1
        wr_norm = max(0, min(1, win_rate))
        # Avg PnL: map -5% to +5% range to 0-1
        pnl_norm = max(0, min(1, (avg_pnl + 5) / 10))

        score = (
            self._config["sharpe_weight"] * sharpe_norm +
            self._config["win_rate_weight"] * wr_norm +
            self._config["pnl_weight"] * pnl_norm
        )
        return score

    def _normalize_to_weights(self, scored):
        """Convert scores to weight multipliers."""
        weights = []
        has_data = [s for s in scored if s["has_data"]]
        no_data = [s for s in scored if not s["has_data"]]

        if has_data:
            avg_score = sum(s["score"] for s in has_data) / len(has_data)
            for s in has_data:
                if avg_score > 0:
                    raw_weight = s["score"] / avg_score
                else:
                    raw_weight = self._config["default_weight"]
                weight = max(
                    self._config["min_weight"],
                    min(self._config["max_weight"], raw_weight),
                )
                weights.append({
                    "strategy_spec_id": s["strategy_spec_id"],
                    "weight": round(weight, 4),
                    "reason": f"score={s['score']:.3f}, raw_weight={raw_weight:.3f}",
                })

        for s in no_data:
            weights.append({
                "strategy_spec_id": s["strategy_spec_id"],
                "weight": self._config["default_weight"],
                "reason": "insufficient trade data, using default weight",
            })

        return weights

    def _apply_smoothing(self, new_weights, regime_type, instrument):
        """Smooth new weights against current weights to avoid whipsawing."""
        current = self._get_current_weights(instrument, regime_type)
        current_map = {w["strategy_spec_id"]: w["weight"] for w in current}
        alpha = self._config["smoothing_factor"]

        smoothed = []
        for w in new_weights:
            sid = w["strategy_spec_id"]
            prev = current_map.get(sid, self._config["default_weight"])
            smoothed_weight = alpha * w["weight"] + (1 - alpha) * float(prev)
            smoothed_weight = max(
                self._config["min_weight"],
                min(self._config["max_weight"], smoothed_weight),
            )
            smoothed.append({
                "strategy_spec_id": sid,
                "weight": round(smoothed_weight, 4),
                "previous_weight": float(prev),
                "reason": w["reason"],
            })
        return smoothed

    # ── Database Operations ─────────────────────────────────────────────

    def _store_weight(self, weight_data):
        """Store a strategy weight record."""
        if not self._conn:
            return
        # Expire previous weight for same strategy/instrument/regime
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE strategy_weights
                SET effective_until = NOW()
                WHERE strategy_spec_id = %s AND instrument = %s
                    AND regime_type = %s AND effective_until IS NULL
                """,
                (
                    weight_data["strategy_spec_id"],
                    weight_data["instrument"],
                    weight_data["regime_type"],
                ),
            )
            cur.execute(
                """
                INSERT INTO strategy_weights (
                    id, strategy_spec_id, instrument, regime_type,
                    weight, previous_weight, reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    weight_data["strategy_spec_id"],
                    weight_data["instrument"],
                    weight_data["regime_type"],
                    weight_data["weight"],
                    weight_data.get("previous_weight"),
                    weight_data.get("reason"),
                ),
            )
        self._conn.commit()

    def _get_current_weights(self, instrument, regime_type):
        """Get current active weights for an instrument/regime."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT strategy_spec_id, weight
                FROM strategy_weights
                WHERE instrument = %s AND regime_type = %s
                    AND effective_until IS NULL
                """,
                (instrument, regime_type),
            )
            if not cur.description:
                return []
            return [
                {"strategy_spec_id": row[0], "weight": row[1]}
                for row in cur.fetchall()
            ]

    def get_all_active_weights(self, instrument):
        """Get all active weights for an instrument across all regimes."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT strategy_spec_id, instrument, regime_type, weight, reason,
                       effective_from
                FROM strategy_weights
                WHERE instrument = %s AND effective_until IS NULL
                ORDER BY weight DESC
                """,
                (instrument,),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
