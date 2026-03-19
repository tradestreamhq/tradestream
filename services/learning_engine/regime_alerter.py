"""Regime Change Alerter — detects and logs market regime transitions.

Compares the current regime to the previous regime for each instrument
and generates alerts when a transition occurs, including which strategies
are favored or unfavored in the new regime.
"""

import json
import uuid
from datetime import datetime, timezone

from absl import logging


class RegimeAlerter:
    """Detects regime changes and generates alerts with strategy recommendations."""

    def __init__(self, db_connection=None):
        self._conn = db_connection

    def check_regime_change(self, instrument, new_regime, previous_regime,
                             favored_strategies=None, unfavored_strategies=None):
        """Check if a regime change has occurred and create an alert.

        Args:
            instrument: Trading instrument.
            new_regime: Dict with regime_type and confidence.
            previous_regime: Dict with regime_type (or None for first detection).
            favored_strategies: List of strategy spec IDs favored in new regime.
            unfavored_strategies: List of strategy spec IDs unfavored in new regime.

        Returns:
            Alert dict if a regime change occurred, None otherwise.
        """
        prev_type = previous_regime.get("regime_type") if previous_regime else None
        new_type = new_regime.get("regime_type")

        if prev_type == new_type:
            return None

        if prev_type is None:
            prev_type = "unknown"

        alert = {
            "instrument": instrument,
            "previous_regime": prev_type,
            "new_regime": new_type,
            "confidence": new_regime.get("confidence", 0.0),
            "favored_strategies": favored_strategies or [],
            "unfavored_strategies": unfavored_strategies or [],
            "alert_metadata": {
                "indicators": new_regime.get("indicators", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        if self._conn:
            self._store_alert(alert)
            self._log_adaptation_event(alert)

        logging.warning(
            "REGIME CHANGE: %s → %s for %s (confidence=%.2f)",
            prev_type, new_type, instrument, alert["confidence"],
        )
        return alert

    def _store_alert(self, alert):
        """Store regime change alert in the database."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO regime_change_alerts (
                    id, instrument, previous_regime, new_regime,
                    confidence, favored_strategies, unfavored_strategies,
                    alert_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    alert["instrument"],
                    alert["previous_regime"],
                    alert["new_regime"],
                    alert["confidence"],
                    json.dumps(alert["favored_strategies"]),
                    json.dumps(alert["unfavored_strategies"]),
                    json.dumps(alert["alert_metadata"]),
                ),
            )
        self._conn.commit()

    def _log_adaptation_event(self, alert):
        """Log a regime change event to the adaptation log."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO adaptation_log (id, event_type, instrument, details)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    "regime_change",
                    alert["instrument"],
                    json.dumps({
                        "previous_regime": alert["previous_regime"],
                        "new_regime": alert["new_regime"],
                        "confidence": alert["confidence"],
                        "favored_count": len(alert["favored_strategies"]),
                        "unfavored_count": len(alert["unfavored_strategies"]),
                    }),
                ),
            )
        self._conn.commit()

    def get_recent_alerts(self, instrument=None, limit=20):
        """Get recent regime change alerts."""
        if not self._conn:
            return []
        if instrument:
            query = """
                SELECT * FROM regime_change_alerts
                WHERE instrument = %s
                ORDER BY created_at DESC LIMIT %s
            """
            params = (instrument, limit)
        else:
            query = """
                SELECT * FROM regime_change_alerts
                ORDER BY created_at DESC LIMIT %s
            """
            params = (limit,)
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def acknowledge_alert(self, alert_id):
        """Mark an alert as acknowledged."""
        if not self._conn:
            return False
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE regime_change_alerts SET acknowledged = TRUE WHERE id = %s",
                (alert_id,),
            )
        self._conn.commit()
        return True
