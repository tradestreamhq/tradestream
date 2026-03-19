"""Strategy Performance Tracker — rolling metrics per strategy per regime.

Tracks rolling Sharpe ratio, win rate, drawdown, and other performance
metrics for each strategy within each market regime.
"""

import json
import math
import uuid
from datetime import datetime, timezone

from absl import logging


class PerformanceTracker:
    """Tracks and stores strategy performance metrics segmented by regime."""

    def __init__(self, db_connection=None):
        self._conn = db_connection

    # ── Metric Calculation ──────────────────────────────────────────────

    def calculate_metrics(self, trades):
        """Calculate performance metrics from a list of trade results.

        Args:
            trades: List of dicts with at least 'pnl_percent' key.
                    Optional: 'hold_duration', 'entry_price', 'exit_price'.

        Returns:
            dict with sharpe_ratio, win_rate, max_drawdown, avg_pnl, etc.
        """
        if not trades:
            return {
                "trade_count": 0,
                "win_count": 0,
                "win_rate": None,
                "avg_pnl_percent": None,
                "total_pnl": None,
                "sharpe_ratio": None,
                "max_drawdown": None,
            }

        pnls = [float(t["pnl_percent"]) for t in trades if t.get("pnl_percent") is not None]
        if not pnls:
            return {
                "trade_count": len(trades),
                "win_count": 0,
                "win_rate": None,
                "avg_pnl_percent": None,
                "total_pnl": None,
                "sharpe_ratio": None,
                "max_drawdown": None,
            }

        trade_count = len(pnls)
        win_count = sum(1 for p in pnls if p > 0)
        win_rate = win_count / trade_count if trade_count > 0 else 0
        avg_pnl = sum(pnls) / trade_count
        total_pnl = sum(pnls)

        sharpe = self._calculate_sharpe(pnls)
        max_dd = self._calculate_max_drawdown(pnls)

        return {
            "trade_count": trade_count,
            "win_count": win_count,
            "win_rate": round(win_rate, 4),
            "avg_pnl_percent": round(avg_pnl, 4),
            "total_pnl": round(total_pnl, 4),
            "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
            "max_drawdown": round(max_dd, 4) if max_dd is not None else None,
        }

    def _calculate_sharpe(self, pnls, risk_free_rate=0.0):
        """Calculate Sharpe ratio from a list of P&L percentages.

        Uses annualized Sharpe assuming daily trades.
        """
        if len(pnls) < 2:
            return None
        mean_ret = sum(pnls) / len(pnls)
        excess = mean_ret - risk_free_rate
        variance = sum((p - mean_ret) ** 2 for p in pnls) / (len(pnls) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return None
        # Annualize assuming ~252 trading days
        return (excess / std) * math.sqrt(252)

    def _calculate_max_drawdown(self, pnls):
        """Calculate maximum drawdown from sequential P&L values."""
        if not pnls:
            return None
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return -max_dd if max_dd > 0 else 0.0

    # ── Per-Strategy-Per-Regime Tracking ────────────────────────────────

    def track_strategy_performance(self, strategy_spec_id, regime_type,
                                    instrument, trades, window_start, window_end):
        """Calculate and store performance metrics for a strategy in a regime.

        Args:
            strategy_spec_id: UUID of the strategy spec.
            regime_type: Current market regime type.
            instrument: Trading instrument.
            trades: List of trade dicts with pnl_percent.
            window_start: Start of the rolling window.
            window_end: End of the rolling window.

        Returns:
            dict with calculated metrics.
        """
        metrics = self.calculate_metrics(trades)
        metrics["strategy_spec_id"] = strategy_spec_id
        metrics["regime_type"] = regime_type
        metrics["instrument"] = instrument
        metrics["window_start"] = window_start
        metrics["window_end"] = window_end

        if self._conn:
            self._store_metrics(metrics)

        logging.info(
            "Tracked performance for strategy %s in %s regime: sharpe=%.2f, wr=%.1f%%",
            strategy_spec_id, regime_type,
            metrics["sharpe_ratio"] or 0,
            (metrics["win_rate"] or 0) * 100,
        )
        return metrics

    def _store_metrics(self, metrics):
        """Store performance metrics in the database."""
        record_id = str(uuid.uuid4())
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_regime_performance (
                    id, strategy_spec_id, regime_type, instrument,
                    window_start, window_end, trade_count, win_count,
                    total_pnl, avg_pnl_percent, sharpe_ratio, max_drawdown, win_rate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record_id,
                    metrics["strategy_spec_id"],
                    metrics["regime_type"],
                    metrics["instrument"],
                    metrics["window_start"],
                    metrics["window_end"],
                    metrics["trade_count"],
                    metrics["win_count"],
                    metrics["total_pnl"],
                    metrics["avg_pnl_percent"],
                    metrics["sharpe_ratio"],
                    metrics["max_drawdown"],
                    metrics["win_rate"],
                ),
            )
        self._conn.commit()

    # ── Query Methods ───────────────────────────────────────────────────

    def get_strategy_performance(self, strategy_spec_id, regime_type=None,
                                  instrument=None, limit=10):
        """Get recent performance records for a strategy."""
        if not self._conn:
            return []
        conditions = ["strategy_spec_id = %s"]
        params = [strategy_spec_id]
        if regime_type:
            conditions.append("regime_type = %s")
            params.append(regime_type)
        if instrument:
            conditions.append("instrument = %s")
            params.append(instrument)
        params.append(limit)
        where = " AND ".join(conditions)
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM strategy_regime_performance
                WHERE {where}
                ORDER BY window_end DESC
                LIMIT %s
                """,
                tuple(params),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_best_strategies_for_regime(self, regime_type, instrument, limit=10):
        """Get the best-performing strategies for a given regime."""
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    strategy_spec_id,
                    AVG(sharpe_ratio) as avg_sharpe,
                    AVG(win_rate) as avg_win_rate,
                    AVG(avg_pnl_percent) as avg_pnl,
                    SUM(trade_count) as total_trades
                FROM strategy_regime_performance
                WHERE regime_type = %s AND instrument = %s
                    AND trade_count >= 5
                GROUP BY strategy_spec_id
                HAVING SUM(trade_count) >= 10
                ORDER BY avg_sharpe DESC NULLS LAST
                LIMIT %s
                """,
                (regime_type, instrument, limit),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_performance_heatmap(self, instrument, limit=20):
        """Get strategy performance heatmap data (strategy x regime).

        Returns a list of records suitable for building a heatmap
        of strategy performance across different regimes.
        """
        if not self._conn:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    strategy_spec_id,
                    regime_type,
                    AVG(sharpe_ratio) as avg_sharpe,
                    AVG(win_rate) as avg_win_rate,
                    AVG(avg_pnl_percent) as avg_pnl,
                    SUM(trade_count) as total_trades
                FROM strategy_regime_performance
                WHERE instrument = %s AND trade_count > 0
                GROUP BY strategy_spec_id, regime_type
                ORDER BY strategy_spec_id, regime_type
                LIMIT %s
                """,
                (instrument, limit),
            )
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
