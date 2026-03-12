"""Learning Engine — Historical Performance Self-Reflection.

Analyzes agent decision history to identify patterns, detect biases,
and generate performance insights that inform future decision-making.
"""

import json
import uuid
from datetime import datetime, timezone

from absl import logging


class HistoricalContext:
    """Context object returned before each new decision."""

    def __init__(
        self,
        recent_decisions=None,
        win_rate=None,
        avg_hold_time=None,
        best_conditions=None,
        worst_conditions=None,
        detected_biases=None,
        pnl_by_confidence=None,
    ):
        self.recent_decisions = recent_decisions or []
        self.win_rate = win_rate
        self.avg_hold_time = avg_hold_time
        self.best_conditions = best_conditions or []
        self.worst_conditions = worst_conditions or []
        self.detected_biases = detected_biases or []
        self.pnl_by_confidence = pnl_by_confidence or {}

    def to_dict(self):
        return {
            "recent_decisions": self.recent_decisions,
            "win_rate": self.win_rate,
            "avg_hold_time": str(self.avg_hold_time) if self.avg_hold_time else None,
            "best_conditions": self.best_conditions,
            "worst_conditions": self.worst_conditions,
            "detected_biases": self.detected_biases,
            "pnl_by_confidence": self.pnl_by_confidence,
        }


class PerformanceReport:
    """Summary report of agent performance over a given period."""

    def __init__(
        self,
        period_start,
        period_end,
        total_decisions,
        total_outcomes,
        win_rate,
        avg_pnl_percent,
        total_pnl,
        max_drawdown,
        best_instrument,
        worst_instrument,
        patterns,
        biases,
    ):
        self.period_start = period_start
        self.period_end = period_end
        self.total_decisions = total_decisions
        self.total_outcomes = total_outcomes
        self.win_rate = win_rate
        self.avg_pnl_percent = avg_pnl_percent
        self.total_pnl = total_pnl
        self.max_drawdown = max_drawdown
        self.best_instrument = best_instrument
        self.worst_instrument = worst_instrument
        self.patterns = patterns
        self.biases = biases

    def to_dict(self):
        return {
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "total_decisions": self.total_decisions,
            "total_outcomes": self.total_outcomes,
            "win_rate": self.win_rate,
            "avg_pnl_percent": self.avg_pnl_percent,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "best_instrument": self.best_instrument,
            "worst_instrument": self.worst_instrument,
            "patterns": self.patterns,
            "biases": self.biases,
        }


# Bias detection thresholds
BIAS_THRESHOLDS = {
    "overconfidence": {
        "min_confidence": 0.7,
        "max_win_rate": 0.5,
        "min_decisions": 5,
    },
    "loss_aversion": {
        "loss_hold_multiplier": 2.0,
        "min_outcomes": 5,
    },
    "recency_bias": {
        "recent_weight_threshold": 0.7,
        "min_decisions": 10,
    },
}


class LearningEngine:
    """Analyzes historical trade performance and generates insights.

    Uses the agent_decisions table (already populated by DecisionLogger)
    and the decision_outcomes table to track and learn from past decisions.
    """

    def __init__(self, db_url=None, connection=None):
        self._db_url = db_url
        self._connection = connection

    def _get_connection(self):
        if self._connection is not None:
            return self._connection, False
        import psycopg2

        conn = psycopg2.connect(self._db_url)
        return conn, True

    def _execute_query(self, query, params=None):
        """Execute a query and return all rows as dicts."""
        conn, should_close = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return []
        finally:
            if should_close:
                conn.close()

    def _execute_write(self, query, params=None):
        """Execute a write query and commit."""
        conn, should_close = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    # ── Decision Outcome Recording ──────────────────────────────────────

    def record_outcome(
        self,
        decision_id,
        instrument,
        action,
        entry_price,
        exit_price,
        exit_timestamp=None,
        hold_duration=None,
        exit_reason=None,
        market_context=None,
        lessons_learned=None,
    ):
        """Record the outcome of a previously logged decision."""
        pnl_absolute = None
        pnl_percent = None
        if entry_price and exit_price and entry_price != 0:
            if action == "BUY":
                pnl_absolute = float(exit_price) - float(entry_price)
            else:
                pnl_absolute = float(entry_price) - float(exit_price)
            pnl_percent = (pnl_absolute / float(entry_price)) * 100

        outcome_id = str(uuid.uuid4())
        self._execute_write(
            """
            INSERT INTO decision_outcomes (
                id, decision_id, instrument, action, entry_price, exit_price,
                exit_timestamp, pnl_absolute, pnl_percent, hold_duration,
                exit_reason, market_context, lessons_learned
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                outcome_id,
                decision_id,
                instrument,
                action,
                entry_price,
                exit_price,
                exit_timestamp or datetime.now(timezone.utc),
                pnl_absolute,
                pnl_percent,
                hold_duration,
                exit_reason,
                json.dumps(market_context) if market_context else None,
                lessons_learned,
            ),
        )
        logging.info(
            "Recorded outcome %s for decision %s: pnl=%.2f%%",
            outcome_id,
            decision_id,
            pnl_percent or 0,
        )
        return outcome_id

    # ── Historical Context Retrieval ────────────────────────────────────

    def get_historical_context(self, instrument, limit=10):
        """Retrieve historical context for an instrument before making a decision."""
        recent = self.get_recent_decisions(instrument, limit=limit)
        win_rate = self.calculate_win_rate(instrument)
        avg_hold = self.calculate_avg_hold_time(instrument)
        best = self.get_best_conditions(instrument)
        worst = self.get_worst_conditions(instrument)
        biases = self.detect_biases(instrument)
        pnl_by_conf = self.get_pnl_by_confidence(instrument)

        return HistoricalContext(
            recent_decisions=recent,
            win_rate=win_rate,
            avg_hold_time=avg_hold,
            best_conditions=best,
            worst_conditions=worst,
            detected_biases=biases,
            pnl_by_confidence=pnl_by_conf,
        )

    def get_recent_decisions(self, instrument, limit=10):
        """Get recent decisions with their outcomes for an instrument."""
        rows = self._execute_query(
            """
            SELECT
                ad.id, ad.created_at, ad.agent_name, ad.decision_type,
                ad.input_context, ad.output, ad.score, ad.reasoning,
                ad.success, ad.model_used,
                do.pnl_percent, do.pnl_absolute, do.hold_duration,
                do.exit_reason, do.entry_price, do.exit_price
            FROM agent_decisions ad
            LEFT JOIN decision_outcomes do ON do.decision_id = ad.id
            WHERE do.instrument = %s OR (
                ad.input_context::text LIKE %s
            )
            ORDER BY ad.created_at DESC
            LIMIT %s
            """,
            (instrument, f"%{instrument}%", limit),
        )
        results = []
        for row in rows:
            results.append(
                {
                    "decision_id": str(row["id"]),
                    "timestamp": (
                        row["created_at"].isoformat() if row["created_at"] else None
                    ),
                    "agent_name": row["agent_name"],
                    "decision_type": row["decision_type"],
                    "score": float(row["score"]) if row["score"] is not None else None,
                    "reasoning": row["reasoning"],
                    "pnl_percent": (
                        float(row["pnl_percent"])
                        if row["pnl_percent"] is not None
                        else None
                    ),
                    "pnl_absolute": (
                        float(row["pnl_absolute"])
                        if row["pnl_absolute"] is not None
                        else None
                    ),
                    "hold_duration": (
                        str(row["hold_duration"]) if row["hold_duration"] else None
                    ),
                    "exit_reason": row["exit_reason"],
                    "success": row["success"],
                }
            )
        return results

    def calculate_win_rate(self, instrument=None):
        """Calculate win rate (outcomes with positive P&L / total outcomes)."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument,) if instrument else ()
        rows = self._execute_query(
            f"""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE do.pnl_percent > 0) as wins
            FROM decision_outcomes do
            {where}
            """,
            params,
        )
        if not rows or rows[0]["total"] == 0:
            return None
        return round(rows[0]["wins"] / rows[0]["total"], 4)

    def calculate_avg_hold_time(self, instrument=None):
        """Calculate average hold time for closed positions."""
        where = (
            "WHERE do.instrument = %s AND do.hold_duration IS NOT NULL"
            if instrument
            else "WHERE do.hold_duration IS NOT NULL"
        )
        params = (instrument,) if instrument else ()
        rows = self._execute_query(
            f"""
            SELECT AVG(EXTRACT(EPOCH FROM do.hold_duration)) as avg_seconds
            FROM decision_outcomes do
            {where}
            """,
            params,
        )
        if not rows or rows[0]["avg_seconds"] is None:
            return None
        return rows[0]["avg_seconds"]

    def get_best_conditions(self, instrument=None, limit=3):
        """Find market conditions that correlated with the best outcomes."""
        where = (
            "WHERE do.instrument = %s AND do.market_context IS NOT NULL"
            if instrument
            else "WHERE do.market_context IS NOT NULL"
        )
        params = (instrument, limit) if instrument else (limit,)
        rows = self._execute_query(
            f"""
            SELECT do.market_context, do.pnl_percent, do.action,
                   do.exit_reason, do.instrument
            FROM decision_outcomes do
            {where}
            AND do.pnl_percent IS NOT NULL
            ORDER BY do.pnl_percent DESC
            LIMIT %s
            """,
            params,
        )
        return [
            {
                "market_context": row["market_context"],
                "pnl_percent": float(row["pnl_percent"]),
                "action": row["action"],
                "instrument": row["instrument"],
            }
            for row in rows
        ]

    def get_worst_conditions(self, instrument=None, limit=3):
        """Find market conditions that correlated with the worst outcomes."""
        where = (
            "WHERE do.instrument = %s AND do.market_context IS NOT NULL"
            if instrument
            else "WHERE do.market_context IS NOT NULL"
        )
        params = (instrument, limit) if instrument else (limit,)
        rows = self._execute_query(
            f"""
            SELECT do.market_context, do.pnl_percent, do.action,
                   do.exit_reason, do.instrument
            FROM decision_outcomes do
            {where}
            AND do.pnl_percent IS NOT NULL
            ORDER BY do.pnl_percent ASC
            LIMIT %s
            """,
            params,
        )
        return [
            {
                "market_context": row["market_context"],
                "pnl_percent": float(row["pnl_percent"]),
                "action": row["action"],
                "instrument": row["instrument"],
            }
            for row in rows
        ]

    def get_pnl_by_confidence(self, instrument=None):
        """Get average P&L bucketed by decision confidence/score level."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument,) if instrument else ()
        rows = self._execute_query(
            f"""
            SELECT
                CASE
                    WHEN ad.score >= 80 THEN 'high'
                    WHEN ad.score >= 50 THEN 'medium'
                    ELSE 'low'
                END as confidence_bucket,
                AVG(do.pnl_percent) as avg_pnl,
                COUNT(*) as count
            FROM decision_outcomes do
            JOIN agent_decisions ad ON ad.id = do.decision_id
            {where}
            AND ad.score IS NOT NULL
            AND do.pnl_percent IS NOT NULL
            GROUP BY confidence_bucket
            """,
            params,
        )
        return {
            row["confidence_bucket"]: {
                "avg_pnl": round(float(row["avg_pnl"]), 4),
                "count": row["count"],
            }
            for row in rows
        }

    # ── Bias Detection ──────────────────────────────────────────────────

    def detect_biases(self, instrument=None):
        """Detect common decision-making biases from historical data."""
        biases = []

        overconf = self._detect_overconfidence(instrument)
        if overconf:
            biases.append(overconf)

        loss_av = self._detect_loss_aversion(instrument)
        if loss_av:
            biases.append(loss_av)

        return biases

    def _detect_overconfidence(self, instrument=None):
        """Detect if high-confidence decisions have low win rates."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument,) if instrument else ()
        rows = self._execute_query(
            f"""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE do.pnl_percent > 0) as wins,
                AVG(ad.score) as avg_score
            FROM decision_outcomes do
            JOIN agent_decisions ad ON ad.id = do.decision_id
            {where}
            AND ad.score >= %s
            """,
            params + (BIAS_THRESHOLDS["overconfidence"]["min_confidence"] * 100,),
        )
        if (
            not rows
            or rows[0]["total"] < BIAS_THRESHOLDS["overconfidence"]["min_decisions"]
        ):
            return None
        win_rate = rows[0]["wins"] / rows[0]["total"]
        if win_rate < BIAS_THRESHOLDS["overconfidence"]["max_win_rate"]:
            return {
                "bias_type": "overconfidence",
                "description": (
                    f"High-confidence decisions (score >= 70) have a win rate of "
                    f"{win_rate:.1%}, suggesting overconfidence."
                ),
                "win_rate": round(win_rate, 4),
                "total_decisions": rows[0]["total"],
                "avg_score": round(float(rows[0]["avg_score"]), 2),
                "mitigation": "Consider reducing position sizes on high-confidence calls or requiring additional confirmation.",
            }
        return None

    def _detect_loss_aversion(self, instrument=None):
        """Detect if losing positions are held longer than winning ones."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument,) if instrument else ()
        rows = self._execute_query(
            f"""
            SELECT
                CASE WHEN do.pnl_percent > 0 THEN 'win' ELSE 'loss' END as outcome,
                AVG(EXTRACT(EPOCH FROM do.hold_duration)) as avg_hold_seconds,
                COUNT(*) as count
            FROM decision_outcomes do
            {where}
            AND do.hold_duration IS NOT NULL
            AND do.pnl_percent IS NOT NULL
            GROUP BY outcome
            """,
            params,
        )
        if len(rows) < 2:
            return None
        by_outcome = {r["outcome"]: r for r in rows}
        if "win" not in by_outcome or "loss" not in by_outcome:
            return None
        total = by_outcome["win"]["count"] + by_outcome["loss"]["count"]
        if total < BIAS_THRESHOLDS["loss_aversion"]["min_outcomes"]:
            return None

        win_hold = by_outcome["win"]["avg_hold_seconds"]
        loss_hold = by_outcome["loss"]["avg_hold_seconds"]
        if win_hold and win_hold > 0:
            ratio = loss_hold / win_hold
            if ratio >= BIAS_THRESHOLDS["loss_aversion"]["loss_hold_multiplier"]:
                return {
                    "bias_type": "loss_aversion",
                    "description": (
                        f"Losing positions are held {ratio:.1f}x longer than winning ones, "
                        f"suggesting loss aversion."
                    ),
                    "loss_hold_avg_seconds": loss_hold,
                    "win_hold_avg_seconds": win_hold,
                    "ratio": round(ratio, 2),
                    "mitigation": "Implement stricter stop-loss rules and time-based exit criteria.",
                }
        return None

    # ── Pattern Detection ───────────────────────────────────────────────

    def detect_patterns(self, instrument=None, min_frequency=3):
        """Detect recurring performance patterns and store them."""
        patterns = []

        # Pattern: Strategy-specific win rates
        strategy_patterns = self._detect_strategy_patterns(instrument, min_frequency)
        patterns.extend(strategy_patterns)

        # Pattern: Time-of-day effects
        time_patterns = self._detect_time_patterns(instrument, min_frequency)
        patterns.extend(time_patterns)

        # Store detected patterns
        for pattern in patterns:
            self._store_pattern(pattern, instrument)

        return patterns

    def _detect_strategy_patterns(self, instrument=None, min_frequency=3):
        """Identify which decision types perform best/worst."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument, min_frequency) if instrument else (min_frequency,)
        rows = self._execute_query(
            f"""
            SELECT
                ad.decision_type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE do.pnl_percent > 0) as wins,
                AVG(do.pnl_percent) as avg_pnl,
                STDDEV(do.pnl_percent) as pnl_stddev
            FROM decision_outcomes do
            JOIN agent_decisions ad ON ad.id = do.decision_id
            {where}
            AND do.pnl_percent IS NOT NULL
            GROUP BY ad.decision_type
            HAVING COUNT(*) >= %s
            ORDER BY avg_pnl DESC
            """,
            params,
        )
        patterns = []
        for row in rows:
            win_rate = row["wins"] / row["total"] if row["total"] > 0 else 0
            avg_pnl = float(row["avg_pnl"]) if row["avg_pnl"] is not None else 0
            pattern_type = "strong_strategy" if avg_pnl > 0 else "weak_strategy"
            patterns.append(
                {
                    "pattern_type": pattern_type,
                    "description": (
                        f"Decision type '{row['decision_type']}' has a {win_rate:.1%} win rate "
                        f"with avg P&L of {avg_pnl:.2f}% over {row['total']} trades."
                    ),
                    "frequency": row["total"],
                    "avg_pnl_impact": avg_pnl,
                    "decision_type": row["decision_type"],
                    "win_rate": round(win_rate, 4),
                }
            )
        return patterns

    def _detect_time_patterns(self, instrument=None, min_frequency=3):
        """Identify if certain hours of the day have better performance."""
        where = "WHERE do.instrument = %s" if instrument else ""
        params = (instrument, min_frequency) if instrument else (min_frequency,)
        rows = self._execute_query(
            f"""
            SELECT
                EXTRACT(HOUR FROM ad.created_at) as hour,
                COUNT(*) as total,
                AVG(do.pnl_percent) as avg_pnl
            FROM decision_outcomes do
            JOIN agent_decisions ad ON ad.id = do.decision_id
            {where}
            AND do.pnl_percent IS NOT NULL
            GROUP BY hour
            HAVING COUNT(*) >= %s
            ORDER BY avg_pnl DESC
            """,
            params,
        )
        patterns = []
        for row in rows:
            avg_pnl = float(row["avg_pnl"]) if row["avg_pnl"] is not None else 0
            if abs(avg_pnl) > 1.0:  # Only flag significant time patterns
                hour = int(row["hour"])
                pattern_type = "favorable_time" if avg_pnl > 0 else "unfavorable_time"
                patterns.append(
                    {
                        "pattern_type": pattern_type,
                        "description": (
                            f"Decisions made around {hour:02d}:00 UTC have avg P&L of "
                            f"{avg_pnl:.2f}% over {row['total']} trades."
                        ),
                        "frequency": row["total"],
                        "avg_pnl_impact": avg_pnl,
                        "hour": hour,
                    }
                )
        return patterns

    def _store_pattern(self, pattern, instrument=None):
        """Store or update a detected pattern in the database."""
        self._execute_write(
            """
            INSERT INTO performance_patterns (
                id, pattern_type, instrument, description,
                frequency, avg_pnl_impact, mitigation_strategy
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                pattern["pattern_type"],
                instrument,
                pattern["description"],
                pattern.get("frequency", 0),
                pattern.get("avg_pnl_impact"),
                pattern.get("mitigation"),
            ),
        )

    def get_stored_patterns(self, instrument=None, limit=20):
        """Retrieve previously detected patterns."""
        if instrument:
            rows = self._execute_query(
                """
                SELECT * FROM performance_patterns
                WHERE instrument = %s OR instrument IS NULL
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
        else:
            rows = self._execute_query(
                """
                SELECT * FROM performance_patterns
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        return rows

    # ── Performance Reports ─────────────────────────────────────────────

    def generate_report(self, period_start=None, period_end=None):
        """Generate a comprehensive performance report."""
        date_filter = ""
        params = []
        if period_start:
            date_filter += " AND do.created_at >= %s"
            params.append(period_start)
        if period_end:
            date_filter += " AND do.created_at <= %s"
            params.append(period_end)

        # Overall metrics
        summary = self._execute_query(
            f"""
            SELECT
                COUNT(DISTINCT ad.id) as total_decisions,
                COUNT(DISTINCT do.id) as total_outcomes,
                COUNT(*) FILTER (WHERE do.pnl_percent > 0) as wins,
                AVG(do.pnl_percent) as avg_pnl,
                SUM(do.pnl_absolute) as total_pnl,
                MIN(do.pnl_percent) as max_loss
            FROM decision_outcomes do
            JOIN agent_decisions ad ON ad.id = do.decision_id
            WHERE do.pnl_percent IS NOT NULL
            {date_filter}
            """,
            tuple(params),
        )

        row = summary[0] if summary else {}
        total_outcomes = row.get("total_outcomes", 0) or 0
        wins = row.get("wins", 0) or 0
        win_rate = round(wins / total_outcomes, 4) if total_outcomes > 0 else None

        # Best/worst instruments
        instrument_stats = self._execute_query(
            f"""
            SELECT
                do.instrument,
                AVG(do.pnl_percent) as avg_pnl,
                COUNT(*) as trades
            FROM decision_outcomes do
            WHERE do.pnl_percent IS NOT NULL
            {date_filter}
            GROUP BY do.instrument
            ORDER BY avg_pnl DESC
            """,
            tuple(params),
        )

        best_instrument = (
            instrument_stats[0]["instrument"] if instrument_stats else None
        )
        worst_instrument = (
            instrument_stats[-1]["instrument"] if instrument_stats else None
        )

        # Max drawdown (simplified: largest peak-to-trough P&L decline)
        max_drawdown = (
            float(row["max_loss"]) if row.get("max_loss") is not None else None
        )

        # Detected biases and patterns
        biases = self.detect_biases()
        patterns = self.detect_patterns()

        return PerformanceReport(
            period_start=period_start,
            period_end=period_end,
            total_decisions=row.get("total_decisions", 0) or 0,
            total_outcomes=total_outcomes,
            win_rate=win_rate,
            avg_pnl_percent=(
                round(float(row["avg_pnl"]), 4)
                if row.get("avg_pnl") is not None
                else None
            ),
            total_pnl=(
                round(float(row["total_pnl"]), 2)
                if row.get("total_pnl") is not None
                else None
            ),
            max_drawdown=max_drawdown,
            best_instrument=best_instrument,
            worst_instrument=worst_instrument,
            patterns=[p for p in patterns],
            biases=biases,
        )

    # ── Self-Reflection Prompt ──────────────────────────────────────────

    def build_reflection_prompt(self, instrument):
        """Build a self-reflection prompt for the agent before making a decision."""
        ctx = self.get_historical_context(instrument)

        sections = [
            f"Before making this decision, review your historical performance on {instrument}:\n"
        ]

        if ctx.win_rate is not None:
            sections.append(f"YOUR WIN RATE: {ctx.win_rate:.1%}")

        if ctx.pnl_by_confidence:
            sections.append("P&L BY CONFIDENCE LEVEL:")
            for bucket, stats in ctx.pnl_by_confidence.items():
                sections.append(
                    f"  {bucket}: avg {stats['avg_pnl']:.2f}% ({stats['count']} trades)"
                )

        if ctx.recent_decisions:
            sections.append(f"\nRECENT DECISIONS ({len(ctx.recent_decisions)}):")
            for d in ctx.recent_decisions[:5]:
                pnl = (
                    f"{d['pnl_percent']:.2f}%"
                    if d.get("pnl_percent") is not None
                    else "pending"
                )
                sections.append(
                    f"  - {d.get('decision_type', 'N/A')}: P&L={pnl}, score={d.get('score', 'N/A')}"
                )

        if ctx.detected_biases:
            sections.append("\nDETECTED BIASES:")
            for b in ctx.detected_biases:
                sections.append(f"  - {b['bias_type']}: {b['description']}")

        if ctx.best_conditions:
            sections.append("\nBEST PERFORMING CONDITIONS:")
            for c in ctx.best_conditions[:2]:
                sections.append(f"  - {c['action']} with P&L={c['pnl_percent']:.2f}%")

        if ctx.worst_conditions:
            sections.append("\nWORST PERFORMING CONDITIONS:")
            for c in ctx.worst_conditions[:2]:
                sections.append(f"  - {c['action']} with P&L={c['pnl_percent']:.2f}%")

        sections.append(
            "\nBased on this self-reflection, adjust your confidence and reasoning accordingly. "
            "What would you do differently this time?"
        )

        return "\n".join(sections)
