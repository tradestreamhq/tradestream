"""Database persistence layer for autonomous pipeline decisions.

Persists AgentDecision records to PostgreSQL for audit trail,
historical analysis, and outcome tracking.
"""

import json
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class DecisionPersistence:
    """Persists autonomous decisions to PostgreSQL.

    Falls back gracefully to in-memory storage if the database
    is unavailable.
    """

    def __init__(self, db_url: str = ""):
        self._db_url = db_url
        self._pool = None
        self._available = False
        if db_url:
            self._init_pool(db_url)

    def _init_pool(self, db_url: str):
        try:
            import psycopg2
            from psycopg2 import pool

            self._pool = pool.SimpleConnectionPool(1, 5, db_url)
            self._available = True
            logger.info("Decision persistence connected to database")
        except Exception as e:
            logger.warning(
                "Database not available, decisions will be in-memory only: %s", e
            )
            self._available = False

    @contextmanager
    def _get_conn(self):
        if not self._pool:
            raise RuntimeError("No database pool")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @property
    def is_available(self) -> bool:
        return self._available

    def persist_decision(self, decision) -> bool:
        """Persist an AgentDecision to the database.

        Returns True if successfully persisted.
        """
        if not self._available:
            return False

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO agent_decisions (
                        decision_id, session_id, user_id, symbol, action,
                        confidence, opportunity_score, opportunity_tier,
                        opportunity_factors, query, symbols_analyzed,
                        reasoning, strategy_breakdown, market_context,
                        tool_calls, validation_status, validation_warnings,
                        max_position_size, model_used, agent_type,
                        latency_ms, tokens_input, tokens_output,
                        created_at, expires_at,
                        risk_approved, risk_rejection_reasons,
                        position_size_pct, fusion_agreement_ratio,
                        conflict_resolution, source_signals
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        decision.decision_id,
                        decision.session_id,
                        decision.user_id,
                        decision.symbol,
                        decision.action,
                        decision.confidence,
                        decision.opportunity_score,
                        decision.opportunity_tier,
                        json.dumps(decision.opportunity_factors),
                        decision.query,
                        decision.symbols_analyzed or [],
                        decision.reasoning,
                        json.dumps(decision.strategy_breakdown),
                        json.dumps(decision.market_context),
                        json.dumps(decision.tool_calls),
                        decision.validation_status,
                        decision.validation_warnings or [],
                        decision.max_position_size,
                        decision.model_used,
                        decision.agent_type,
                        decision.latency_ms,
                        decision.tokens_input,
                        decision.tokens_output,
                        decision.created_at,
                        decision.expires_at,
                        decision.risk_approved,
                        decision.risk_rejection_reasons or [],
                        decision.position_size_pct,
                        decision.fusion_agreement_ratio,
                        decision.conflict_resolution,
                        json.dumps(
                            [
                                {
                                    "source": s.source,
                                    "action": s.action.value,
                                    "confidence": s.confidence,
                                }
                                for s in decision.source_signals
                            ]
                            if decision.source_signals
                            else []
                        ),
                    ),
                )
            return True
        except Exception as e:
            logger.error("Failed to persist decision %s: %s", decision.decision_id, e)
            return False

    def get_recent_decisions(
        self, limit: int = 50, symbol: Optional[str] = None
    ) -> list:
        """Retrieve recent decisions from the database."""
        if not self._available:
            return []

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                if symbol:
                    cur.execute(
                        """
                        SELECT decision_id, symbol, action, confidence,
                               opportunity_score, opportunity_tier, reasoning,
                               risk_approved, latency_ms, created_at
                        FROM agent_decisions
                        WHERE symbol = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (symbol, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT decision_id, symbol, action, confidence,
                               opportunity_score, opportunity_tier, reasoning,
                               risk_approved, latency_ms, created_at
                        FROM agent_decisions
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (limit,),
                    )

                rows = cur.fetchall()
                return [
                    {
                        "decision_id": row[0],
                        "symbol": row[1],
                        "action": row[2],
                        "confidence": float(row[3]),
                        "opportunity_score": float(row[4]),
                        "opportunity_tier": row[5],
                        "reasoning": row[6],
                        "risk_approved": row[7],
                        "latency_ms": row[8],
                        "created_at": row[9].isoformat() if row[9] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error("Failed to query decisions: %s", e)
            return []

    def record_outcome(
        self,
        decision_id: str,
        actual_return: float,
        hit_target: bool,
        exit_price: Optional[float] = None,
        max_drawdown: Optional[float] = None,
    ) -> bool:
        """Record the outcome of a decision for learning."""
        if not self._available:
            return False

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO decision_outcomes (
                        decision_id, actual_return, hit_target,
                        exit_price, max_drawdown, recorded_by
                    ) VALUES (%s, %s, %s, %s, %s, 'autonomous_runner')
                    ON CONFLICT (decision_id) DO UPDATE SET
                        actual_return = EXCLUDED.actual_return,
                        hit_target = EXCLUDED.hit_target,
                        exit_price = EXCLUDED.exit_price,
                        max_drawdown = EXCLUDED.max_drawdown
                    """,
                    (decision_id, actual_return, hit_target, exit_price, max_drawdown),
                )
                cur.execute(
                    """
                    UPDATE agent_decisions
                    SET outcome_recorded = TRUE,
                        actual_return = %s,
                        hit_target = %s
                    WHERE decision_id = %s
                    """,
                    (actual_return, hit_target, decision_id),
                )
            return True
        except Exception as e:
            logger.error("Failed to record outcome for %s: %s", decision_id, e)
            return False

    def close(self):
        if self._pool:
            self._pool.closeall()
