"""Decision query functions for analytics and dashboard.

Implements the query patterns defined in specs/agent-decisions-schema/SPEC.md:
- Dashboard queries (recent high-opportunity decisions)
- Symbol-specific queries
- Tool call performance analysis
- Model usage tracking
- Outcome accuracy calculations
"""

import json
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class DecisionQueryService:
    """Executes analytics queries against the agent_decisions schema.

    Works with an existing database connection pool (from DecisionPersistence
    or injected directly). Falls back gracefully when DB is unavailable.
    """

    def __init__(self, db_pool=None):
        self._pool = db_pool

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    @contextmanager
    def _get_conn(self):
        if not self._pool:
            raise RuntimeError("No database pool")
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def get_dashboard_decisions(
        self,
        hours: int = 24,
        min_opportunity_score: float = 0.0,
        limit: int = 50,
    ) -> list:
        """Get recent high-opportunity BUY/SELL decisions for dashboard.

        Uses idx_agent_decisions_dashboard composite index.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        decision_id, symbol, action, confidence,
                        opportunity_score, opportunity_tier,
                        reasoning, strategy_breakdown, created_at
                    FROM agent_decisions
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                      AND action IN ('BUY', 'SELL')
                      AND opportunity_score >= %s
                    ORDER BY opportunity_score DESC, created_at DESC
                    LIMIT %s
                    """,
                    (hours, min_opportunity_score, limit),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "decision_id",
                        "symbol",
                        "action",
                        "confidence",
                        "opportunity_score",
                        "opportunity_tier",
                        "reasoning",
                        "strategy_breakdown",
                        "created_at",
                    ],
                )
        except Exception as e:
            logger.error("Dashboard query failed: %s", e)
            return []

    def get_decisions_by_symbol(
        self, symbol: str, days: int = 7, limit: int = 20
    ) -> list:
        """Get recent decisions for a specific symbol.

        Uses idx_agent_decisions_symbol index.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        decision_id, symbol, action, confidence,
                        opportunity_score, opportunity_tier,
                        reasoning, strategy_breakdown, market_context,
                        tool_calls, risk_approved, latency_ms, created_at
                    FROM agent_decisions
                    WHERE symbol = %s
                      AND created_at >= NOW() - INTERVAL '%s days'
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (symbol, days, limit),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "decision_id",
                        "symbol",
                        "action",
                        "confidence",
                        "opportunity_score",
                        "opportunity_tier",
                        "reasoning",
                        "strategy_breakdown",
                        "market_context",
                        "tool_calls",
                        "risk_approved",
                        "latency_ms",
                        "created_at",
                    ],
                )
        except Exception as e:
            logger.error("Symbol query failed for %s: %s", symbol, e)
            return []

    def get_high_opportunity_decisions(
        self, min_score: float = 80.0, hours: int = 1
    ) -> list:
        """Get high-opportunity decisions from the last N hours.

        Uses idx_agent_decisions_opportunity index.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        decision_id, symbol, action, confidence,
                        opportunity_score, opportunity_tier,
                        reasoning, created_at
                    FROM agent_decisions
                    WHERE opportunity_score >= %s
                      AND created_at >= NOW() - INTERVAL '%s hours'
                    ORDER BY opportunity_score DESC
                    """,
                    (min_score, hours),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "decision_id",
                        "symbol",
                        "action",
                        "confidence",
                        "opportunity_score",
                        "opportunity_tier",
                        "reasoning",
                        "created_at",
                    ],
                )
        except Exception as e:
            logger.error("High opportunity query failed: %s", e)
            return []

    def analyze_tool_performance(self, hours: int = 24) -> list:
        """Analyze tool call latency and frequency.

        Uses GIN index on tool_calls JSONB for efficient queries.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        tool_call->>'tool' as tool_name,
                        AVG((tool_call->>'latency_ms')::int) as avg_latency_ms,
                        COUNT(*) as call_count
                    FROM agent_decisions,
                         jsonb_array_elements(tool_calls->'calls') as tool_call
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                    GROUP BY tool_call->>'tool'
                    ORDER BY avg_latency_ms DESC
                    """,
                    (hours,),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    ["tool_name", "avg_latency_ms", "call_count"],
                )
        except Exception as e:
            logger.error("Tool performance query failed: %s", e)
            return []

    def track_model_usage(self, hours: int = 24) -> list:
        """Track model usage statistics.

        Groups decisions by model_used and agent_type.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        model_used,
                        agent_type,
                        COUNT(*) as decisions,
                        AVG(latency_ms) as avg_latency_ms,
                        COALESCE(SUM(tokens_input), 0) as total_input_tokens,
                        COALESCE(SUM(tokens_output), 0) as total_output_tokens
                    FROM agent_decisions
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                    GROUP BY model_used, agent_type
                    ORDER BY decisions DESC
                    """,
                    (hours,),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "model_used",
                        "agent_type",
                        "decisions",
                        "avg_latency_ms",
                        "total_input_tokens",
                        "total_output_tokens",
                    ],
                )
        except Exception as e:
            logger.error("Model usage query failed: %s", e)
            return []

    def calculate_accuracy(self, days: int = 30) -> list:
        """Calculate decision accuracy using the separate outcomes table.

        Joins agent_decisions with decision_outcomes to compute hit rates
        per symbol and action.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        d.symbol,
                        d.action,
                        COUNT(*) as total_decisions,
                        COUNT(*) FILTER (WHERE o.hit_target = TRUE) as correct_decisions,
                        CASE WHEN COUNT(*) > 0
                            THEN COUNT(*) FILTER (WHERE o.hit_target = TRUE)::float / COUNT(*)
                            ELSE 0
                        END as accuracy,
                        AVG(o.actual_return) as avg_return,
                        AVG(o.max_drawdown) as avg_drawdown
                    FROM agent_decisions d
                    JOIN decision_outcomes o ON d.decision_id = o.decision_id
                    WHERE d.created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY d.symbol, d.action
                    ORDER BY accuracy DESC
                    """,
                    (days,),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "symbol",
                        "action",
                        "total_decisions",
                        "correct_decisions",
                        "accuracy",
                        "avg_return",
                        "avg_drawdown",
                    ],
                )
        except Exception as e:
            logger.error("Accuracy query failed: %s", e)
            return []

    def find_decisions_by_tool(self, tool_name: str, limit: int = 20) -> list:
        """Find decisions that used a specific tool (GIN index query).

        Uses JSONB containment operator @> for efficient GIN index lookup.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT decision_id, symbol, action, confidence,
                           opportunity_score, latency_ms, created_at
                    FROM agent_decisions
                    WHERE tool_calls @> %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (json.dumps({"tools_called": [tool_name]}), limit),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "decision_id",
                        "symbol",
                        "action",
                        "confidence",
                        "opportunity_score",
                        "latency_ms",
                        "created_at",
                    ],
                )
        except Exception as e:
            logger.error("Tool search query failed: %s", e)
            return []

    def find_decisions_by_strategy(self, strategy_name: str, limit: int = 20) -> list:
        """Find decisions that used a specific strategy (GIN index query).

        Uses strategy_breakdown JSONB containment for efficient lookup.
        """
        if not self.is_available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT decision_id, symbol, action, confidence,
                           opportunity_score, strategy_breakdown, created_at
                    FROM agent_decisions
                    WHERE strategy_breakdown @> %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (json.dumps({"top_strategy": strategy_name}), limit),
                )
                return _rows_to_dicts(
                    cur.fetchall(),
                    [
                        "decision_id",
                        "symbol",
                        "action",
                        "confidence",
                        "opportunity_score",
                        "strategy_breakdown",
                        "created_at",
                    ],
                )
        except Exception as e:
            logger.error("Strategy search query failed: %s", e)
            return []


def _rows_to_dicts(rows: list, columns: list) -> list:
    """Convert cursor rows to list of dicts with proper serialization."""
    result = []
    for row in rows:
        d = {}
        for i, col in enumerate(columns):
            val = row[i]
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            elif isinstance(val, float):
                val = round(val, 4)
            d[col] = val
        result.append(d)
    return result
