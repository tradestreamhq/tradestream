"""Decision Logger - shared client library for logging agent decisions to PostgreSQL."""

import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from absl import logging


class DecisionLogger:
    """Logs agent decisions to the agent_decisions table in PostgreSQL.

    Usage:
        logger = DecisionLogger(db_url="postgresql://...")

        # Direct logging
        logger.log_decision(
            agent_name="signal_generator",
            decision_type="signal_emission",
            input_context={"symbol": "BTC-USD", "strategies": [...]},
            output={"action": "BUY", "confidence": 0.8},
            model_used="claude-3-5-haiku",
        )

        # Context manager for automatic latency/success tracking
        with logger.track("signal_generator", "signal_emission") as ctx:
            ctx.input_context = {"symbol": "BTC-USD"}
            result = do_work()
            ctx.output = result
            ctx.model_used = "claude-3-5-haiku"
            ctx.tokens_used = 1500
    """

    def __init__(self, db_url=None, connection=None):
        """Initialize with either a database URL or an existing connection.

        Args:
            db_url: PostgreSQL connection string.
            connection: An existing psycopg2 connection object.
        """
        self._db_url = db_url
        self._connection = connection

    def _get_connection(self):
        if self._connection is not None:
            return self._connection, False
        import psycopg2

        conn = psycopg2.connect(self._db_url)
        return conn, True

    def log_decision(
        self,
        agent_name,
        decision_type,
        input_context=None,
        output=None,
        signal_id=None,
        score=None,
        tier=None,
        reasoning=None,
        tool_calls=None,
        model_used=None,
        latency_ms=None,
        tokens_used=None,
        success=True,
        error_message=None,
        parent_decision_id=None,
    ):
        """Insert a decision record into the agent_decisions table.

        Returns the UUID of the inserted decision.
        """
        decision_id = str(uuid.uuid4())
        conn, should_close = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_decisions (
                        id, signal_id, score, tier, reasoning, tool_calls,
                        model_used, latency_ms, tokens_used, created_at,
                        agent_name, decision_type, input_context, output,
                        success, error_message, parent_decision_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        decision_id,
                        signal_id,
                        score,
                        tier,
                        reasoning,
                        json.dumps(tool_calls) if tool_calls is not None else None,
                        model_used,
                        latency_ms,
                        tokens_used,
                        datetime.now(timezone.utc),
                        agent_name,
                        decision_type,
                        (
                            json.dumps(input_context)
                            if input_context is not None
                            else None
                        ),
                        json.dumps(output) if output is not None else None,
                        success,
                        error_message,
                        parent_decision_id,
                    ),
                )
            conn.commit()
            logging.info(
                "Logged decision %s: agent=%s type=%s success=%s",
                decision_id,
                agent_name,
                decision_type,
                success,
            )
            return decision_id
        except Exception:
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def log_signal_decision(
        self,
        signal_id=None,
        input_context=None,
        output=None,
        score=None,
        tier=None,
        reasoning=None,
        tool_calls=None,
        model_used=None,
        latency_ms=None,
        tokens_used=None,
        success=True,
        error_message=None,
        parent_decision_id=None,
    ):
        """Log a signal generation decision."""
        return self.log_decision(
            agent_name="signal_generator",
            decision_type="signal_emission",
            signal_id=signal_id,
            input_context=input_context,
            output=output,
            score=score,
            tier=tier,
            reasoning=reasoning,
            tool_calls=tool_calls,
            model_used=model_used,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            success=success,
            error_message=error_message,
            parent_decision_id=parent_decision_id,
        )

    def log_scoring_decision(
        self,
        signal_id=None,
        input_context=None,
        output=None,
        score=None,
        tier=None,
        reasoning=None,
        tool_calls=None,
        model_used=None,
        latency_ms=None,
        tokens_used=None,
        success=True,
        error_message=None,
        parent_decision_id=None,
    ):
        """Log an opportunity scoring decision."""
        return self.log_decision(
            agent_name="opportunity_scorer",
            decision_type="scoring",
            signal_id=signal_id,
            input_context=input_context,
            output=output,
            score=score,
            tier=tier,
            reasoning=reasoning,
            tool_calls=tool_calls,
            model_used=model_used,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            success=success,
            error_message=error_message,
            parent_decision_id=parent_decision_id,
        )

    def log_proposal_decision(
        self,
        input_context=None,
        output=None,
        reasoning=None,
        tool_calls=None,
        model_used=None,
        latency_ms=None,
        tokens_used=None,
        success=True,
        error_message=None,
        parent_decision_id=None,
    ):
        """Log a strategy proposal decision."""
        return self.log_decision(
            agent_name="strategy_proposer",
            decision_type="strategy_proposal",
            input_context=input_context,
            output=output,
            reasoning=reasoning,
            tool_calls=tool_calls,
            model_used=model_used,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            success=success,
            error_message=error_message,
            parent_decision_id=parent_decision_id,
        )

    def log_orchestration_decision(
        self,
        decision_type="scheduling",
        input_context=None,
        output=None,
        reasoning=None,
        tool_calls=None,
        model_used=None,
        latency_ms=None,
        tokens_used=None,
        success=True,
        error_message=None,
    ):
        """Log an orchestrator decision (scheduling, retry, circuit_break)."""
        return self.log_decision(
            agent_name="orchestrator",
            decision_type=decision_type,
            input_context=input_context,
            output=output,
            reasoning=reasoning,
            tool_calls=tool_calls,
            model_used=model_used,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            success=success,
            error_message=error_message,
        )

    @contextmanager
    def track(self, agent_name, decision_type, parent_decision_id=None):
        """Context manager that automatically tracks latency and success.

        Usage:
            with logger.track("signal_generator", "signal_emission") as ctx:
                ctx.input_context = {"symbol": "BTC-USD"}
                result = do_work()
                ctx.output = result
                ctx.model_used = "claude-3-5-haiku"
                ctx.tokens_used = 1500
        """
        ctx = _TrackingContext(agent_name, decision_type, parent_decision_id)
        start = time.monotonic()
        try:
            yield ctx
            ctx._success = True
        except Exception as exc:
            ctx._success = False
            ctx._error_message = str(exc)
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            try:
                self.log_decision(
                    agent_name=agent_name,
                    decision_type=decision_type,
                    signal_id=ctx.signal_id,
                    input_context=ctx.input_context,
                    output=ctx.output,
                    score=ctx.score,
                    tier=ctx.tier,
                    reasoning=ctx.reasoning,
                    tool_calls=ctx.tool_calls,
                    model_used=ctx.model_used,
                    latency_ms=elapsed_ms,
                    tokens_used=ctx.tokens_used,
                    success=ctx._success,
                    error_message=ctx._error_message,
                    parent_decision_id=parent_decision_id,
                )
            except Exception as log_err:
                logging.error("Failed to log decision: %s", log_err)


class _TrackingContext:
    """Mutable context object used inside the `track` context manager."""

    def __init__(self, agent_name, decision_type, parent_decision_id=None):
        self.agent_name = agent_name
        self.decision_type = decision_type
        self.parent_decision_id = parent_decision_id
        self.signal_id = None
        self.input_context = None
        self.output = None
        self.score = None
        self.tier = None
        self.reasoning = None
        self.tool_calls = None
        self.model_used = None
        self.tokens_used = None
        self._success = True
        self._error_message = None
