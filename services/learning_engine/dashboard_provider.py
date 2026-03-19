"""Dashboard Data Provider — aggregates learning engine data for display.

Provides structured data for the learning dashboard:
  - Regime history timeline
  - Strategy performance heatmap (strategy x regime)
  - Adaptation audit log
  - Current weights and active adaptations
"""

import json
from datetime import datetime, timezone

from absl import logging


class DashboardProvider:
    """Aggregates learning engine data for dashboard consumption."""

    def __init__(self, db_connection=None):
        self._conn = db_connection

    def get_dashboard_data(self, instrument, limit=50):
        """Get all dashboard data for an instrument in a single call.

        Returns:
            dict with regime_history, performance_heatmap, adaptation_log,
            current_weights, recent_alerts.
        """
        return {
            "instrument": instrument,
            "regime_history": self.get_regime_history(instrument, limit),
            "performance_heatmap": self.get_performance_heatmap(instrument),
            "adaptation_log": self.get_adaptation_log(instrument, limit),
            "current_weights": self.get_current_weights(instrument),
            "recent_alerts": self.get_recent_alerts(instrument, limit=10),
            "regime_summary": self.get_regime_summary(instrument),
        }

    def get_regime_history(self, instrument, limit=50):
        """Get regime history timeline for an instrument."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, instrument, regime_type, confidence, indicators,
                       started_at, ended_at,
                       EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))
                           as duration_seconds
                FROM market_regimes
                WHERE instrument = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_performance_heatmap(self, instrument):
        """Get strategy performance data organized by regime.

        Returns a matrix-like structure: [{strategy_spec_id, regime_type,
        avg_sharpe, avg_win_rate, avg_pnl, total_trades}, ...]
        """
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    srp.strategy_spec_id,
                    ss.name as strategy_name,
                    srp.regime_type,
                    AVG(srp.sharpe_ratio) as avg_sharpe,
                    AVG(srp.win_rate) as avg_win_rate,
                    AVG(srp.avg_pnl_percent) as avg_pnl,
                    SUM(srp.trade_count) as total_trades
                FROM strategy_regime_performance srp
                LEFT JOIN strategy_specs ss ON ss.id = srp.strategy_spec_id
                WHERE srp.instrument = %s AND srp.trade_count > 0
                GROUP BY srp.strategy_spec_id, ss.name, srp.regime_type
                ORDER BY ss.name, srp.regime_type
                """,
                (instrument,),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_adaptation_log(self, instrument=None, limit=50):
        """Get the adaptation audit log."""
        if not self._conn:
            return []
        if instrument:
            query = """
                SELECT id, event_type, instrument, strategy_spec_id,
                       details, created_at
                FROM adaptation_log
                WHERE instrument = %s
                ORDER BY created_at DESC LIMIT %s
            """
            params = (instrument, limit)
        else:
            query = """
                SELECT id, event_type, instrument, strategy_spec_id,
                       details, created_at
                FROM adaptation_log
                ORDER BY created_at DESC LIMIT %s
            """
            params = (limit,)
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_current_weights(self, instrument):
        """Get current active strategy weights."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    sw.strategy_spec_id,
                    ss.name as strategy_name,
                    sw.regime_type,
                    sw.weight,
                    sw.previous_weight,
                    sw.reason,
                    sw.effective_from
                FROM strategy_weights sw
                LEFT JOIN strategy_specs ss ON ss.id = sw.strategy_spec_id
                WHERE sw.instrument = %s AND sw.effective_until IS NULL
                ORDER BY sw.weight DESC
                """,
                (instrument,),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_recent_alerts(self, instrument=None, limit=10):
        """Get recent regime change alerts."""
        if not self._conn:
            return []
        if instrument:
            query = """
                SELECT id, instrument, previous_regime, new_regime,
                       confidence, favored_strategies, unfavored_strategies,
                       acknowledged, created_at
                FROM regime_change_alerts
                WHERE instrument = %s
                ORDER BY created_at DESC LIMIT %s
            """
            params = (instrument, limit)
        else:
            query = """
                SELECT id, instrument, previous_regime, new_regime,
                       confidence, favored_strategies, unfavored_strategies,
                       acknowledged, created_at
                FROM regime_change_alerts
                ORDER BY created_at DESC LIMIT %s
            """
            params = (limit,)
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_regime_summary(self, instrument):
        """Get a summary of time spent in each regime."""
        if not self._conn:
            return {}
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    regime_type,
                    COUNT(*) as occurrences,
                    AVG(EXTRACT(EPOCH FROM
                        (COALESCE(ended_at, NOW()) - started_at))) as avg_duration_seconds,
                    SUM(EXTRACT(EPOCH FROM
                        (COALESCE(ended_at, NOW()) - started_at))) as total_duration_seconds
                FROM market_regimes
                WHERE instrument = %s
                GROUP BY regime_type
                ORDER BY total_duration_seconds DESC
                """,
                (instrument,),
            )
            if not cur.description:
                return {}
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            return {row["regime_type"]: row for row in rows}
