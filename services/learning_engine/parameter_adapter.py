"""Parameter Adapter — adjusts strategy parameters based on market regime.

Applies regime-specific adaptations to strategy parameters:
  - Volatile regime: wider stops, reduced position size, shorter timeframes
  - Quiet regime: tighter stops, longer holding periods
  - Trending regime: wider trailing stops, momentum-aligned entries
  - Ranging regime: mean-reversion friendly parameters
"""

import json
import uuid
from datetime import datetime, timezone

from absl import logging


# Default adaptation rules per regime type.
DEFAULT_ADAPTATION_RULES = {
    "volatile": {
        "stop_loss_multiplier": 1.5,
        "take_profit_multiplier": 1.3,
        "position_size_multiplier": 0.7,
        "lookback_period_multiplier": 0.8,
        "description": "Wider stops and smaller positions for volatile markets",
    },
    "quiet": {
        "stop_loss_multiplier": 0.7,
        "take_profit_multiplier": 0.8,
        "position_size_multiplier": 1.2,
        "lookback_period_multiplier": 1.3,
        "description": "Tighter stops and larger positions for quiet markets",
    },
    "trending_up": {
        "stop_loss_multiplier": 1.2,
        "take_profit_multiplier": 1.5,
        "position_size_multiplier": 1.1,
        "lookback_period_multiplier": 1.0,
        "description": "Extended targets with moderate stops for uptrends",
    },
    "trending_down": {
        "stop_loss_multiplier": 1.2,
        "take_profit_multiplier": 1.5,
        "position_size_multiplier": 0.9,
        "lookback_period_multiplier": 1.0,
        "description": "Extended targets with moderate stops for downtrends",
    },
    "ranging": {
        "stop_loss_multiplier": 0.9,
        "take_profit_multiplier": 0.9,
        "position_size_multiplier": 1.0,
        "lookback_period_multiplier": 1.1,
        "description": "Tighter targets suited for mean reversion in ranging markets",
    },
}

# Keys in strategy parameters that can be adapted.
ADAPTABLE_KEYS = {
    "stop_loss": "stop_loss_multiplier",
    "stop_loss_percent": "stop_loss_multiplier",
    "take_profit": "take_profit_multiplier",
    "take_profit_percent": "take_profit_multiplier",
    "position_size": "position_size_multiplier",
    "position_size_percent": "position_size_multiplier",
    "lookback_period": "lookback_period_multiplier",
    "lookback": "lookback_period_multiplier",
    "period": "lookback_period_multiplier",
    "window": "lookback_period_multiplier",
}


class ParameterAdapter:
    """Adapts strategy parameters based on the current market regime."""

    def __init__(self, db_connection=None, rules=None):
        self._conn = db_connection
        self._rules = rules or DEFAULT_ADAPTATION_RULES

    def adapt_parameters(self, strategy_spec_id, original_parameters,
                          regime_type, instrument):
        """Adapt strategy parameters for the given regime.

        Args:
            strategy_spec_id: UUID of the strategy.
            original_parameters: Dict of current strategy parameters.
            regime_type: Current market regime type.
            instrument: Trading instrument.

        Returns:
            dict with original_parameters, adapted_parameters, and
            which rules were applied.
        """
        if regime_type not in self._rules:
            return {
                "strategy_spec_id": strategy_spec_id,
                "original_parameters": original_parameters,
                "adapted_parameters": original_parameters,
                "rules_applied": [],
                "regime_type": regime_type,
            }

        rules = self._rules[regime_type]
        adapted = dict(original_parameters)
        rules_applied = []

        for param_key, param_value in original_parameters.items():
            multiplier_key = ADAPTABLE_KEYS.get(param_key)
            if multiplier_key and multiplier_key in rules:
                multiplier = rules[multiplier_key]
                try:
                    original_val = float(param_value)
                    adapted_val = round(original_val * multiplier, 6)
                    adapted[param_key] = adapted_val
                    rules_applied.append({
                        "parameter": param_key,
                        "original_value": original_val,
                        "adapted_value": adapted_val,
                        "multiplier": multiplier,
                        "rule": multiplier_key,
                    })
                except (ValueError, TypeError):
                    pass

        result = {
            "strategy_spec_id": strategy_spec_id,
            "original_parameters": original_parameters,
            "adapted_parameters": adapted,
            "rules_applied": rules_applied,
            "regime_type": regime_type,
            "instrument": instrument,
            "description": rules.get("description", ""),
        }

        if self._conn and rules_applied:
            self._store_adaptation(result)

        logging.info(
            "Adapted %d parameters for strategy %s in %s regime",
            len(rules_applied), strategy_spec_id, regime_type,
        )
        return result

    def get_adapted_parameters(self, strategy_spec_id, instrument):
        """Get the currently active adapted parameters for a strategy."""
        if not self._conn:
            return None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT adapted_parameters, regime_type, adaptation_rules
                FROM parameter_adaptations
                WHERE strategy_spec_id = %s AND instrument = %s
                    AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
                """,
                (strategy_spec_id, instrument),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "adapted_parameters": row[0],
                "regime_type": row[1],
                "adaptation_rules": row[2],
            }

    def revert_adaptation(self, strategy_spec_id, instrument):
        """Revert active adaptations for a strategy."""
        if not self._conn:
            return False
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE parameter_adaptations
                SET status = 'reverted', updated_at = NOW()
                WHERE strategy_spec_id = %s AND instrument = %s
                    AND status = 'active'
                """,
                (strategy_spec_id, instrument),
            )
        self._conn.commit()
        return True

    def _store_adaptation(self, result):
        """Store parameter adaptation in the database."""
        # Supersede existing active adaptations
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE parameter_adaptations
                SET status = 'superseded', updated_at = NOW()
                WHERE strategy_spec_id = %s AND instrument = %s
                    AND status = 'active'
                """,
                (result["strategy_spec_id"], result["instrument"]),
            )
            cur.execute(
                """
                INSERT INTO parameter_adaptations (
                    id, strategy_spec_id, instrument, regime_type,
                    original_parameters, adapted_parameters, adaptation_rules
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    result["strategy_spec_id"],
                    result["instrument"],
                    result["regime_type"],
                    json.dumps(result["original_parameters"]),
                    json.dumps(result["adapted_parameters"]),
                    json.dumps(result["rules_applied"]),
                ),
            )
        self._conn.commit()

    def get_adaptation_history(self, strategy_spec_id=None, instrument=None,
                               limit=20):
        """Get adaptation history for dashboard display."""
        if not self._conn:
            return []
        conditions = []
        params = []
        if strategy_spec_id:
            conditions.append("strategy_spec_id = %s")
            params.append(strategy_spec_id)
        if instrument:
            conditions.append("instrument = %s")
            params.append(instrument)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, strategy_spec_id, instrument, regime_type,
                       original_parameters, adapted_parameters, adaptation_rules,
                       status, created_at
                FROM parameter_adaptations
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
