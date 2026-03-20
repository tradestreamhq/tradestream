"""
PostgreSQL client for the decisions MCP server.
Handles connection management and decision queries against the agent_decisions table.
Uses the spec-compliant schema with decision_id primary key.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

postgres_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (
            asyncpg.ConnectionDoesNotExistError,
            asyncpg.ConnectionFailureError,
            asyncpg.QueryCanceledError,
            asyncpg.PostgresError,
        )
    ),
    reraise=True,
)


class PostgresClient:
    """Async PostgreSQL client for decisions MCP queries."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool: Optional[asyncpg.Pool] = None

    @retry(**postgres_retry_params)
    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            logging.info(
                f"Connecting to PostgreSQL at {self.host}:{self.port}/{self.database}"
            )

            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
                server_settings={
                    "application_name": "decisions_mcp",
                },
            )

            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")

            logging.info("Successfully connected to PostgreSQL")
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
            self.pool = None
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    async def get_recent_decisions(
        self,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        min_opportunity_score: float = 0,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get recent agent decisions with optional filters."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = ["created_at >= NOW() - INTERVAL '24 hours'"]
        params: List[Any] = []
        param_idx = 1

        if min_opportunity_score > 0:
            conditions.append(f"opportunity_score >= ${param_idx}")
            params.append(min_opportunity_score)
            param_idx += 1

        if symbol:
            conditions.append(f"symbol = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        if action:
            conditions.append(f"action = ${param_idx}")
            params.append(action)
            param_idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT decision_id, session_id, user_id, symbol, action,
               confidence, opportunity_score, opportunity_tier,
               opportunity_factors, reasoning, strategy_breakdown,
               market_context, tool_calls, validation_status,
               model_used, agent_type, latency_ms, created_at
        FROM agent_decisions
        {where_clause}
        ORDER BY opportunity_score DESC, created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        count_query = f"""
        SELECT COUNT(*) FROM agent_decisions {where_clause}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[: param_idx - 1])

        items = []
        for row in rows:
            tool_calls = row["tool_calls"]
            if isinstance(tool_calls, str):
                tool_calls = json.loads(tool_calls)

            items.append(
                {
                    "decision_id": str(row["decision_id"]),
                    "session_id": (
                        str(row["session_id"]) if row["session_id"] else None
                    ),
                    "symbol": row["symbol"],
                    "action": row["action"],
                    "confidence": float(row["confidence"]),
                    "opportunity_score": (
                        float(row["opportunity_score"])
                        if row["opportunity_score"]
                        else None
                    ),
                    "opportunity_tier": row["opportunity_tier"],
                    "reasoning": row["reasoning"],
                    "strategy_breakdown": row["strategy_breakdown"],
                    "market_context": row["market_context"],
                    "tool_calls": tool_calls,
                    "validation_status": row["validation_status"],
                    "model_used": row["model_used"],
                    "agent_type": row["agent_type"],
                    "latency_ms": row["latency_ms"],
                    "created_at": str(row["created_at"]),
                }
            )

        return {
            "items": items,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more": offset + limit < total,
            },
        }

    async def save_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        reasoning: str,
        opportunity_score: Optional[float] = None,
        opportunity_tier: Optional[str] = None,
        opportunity_factors: Optional[Dict] = None,
        strategy_breakdown: Optional[Dict] = None,
        market_context: Optional[Dict] = None,
        tool_calls: Optional[Dict] = None,
        validation_status: Optional[str] = None,
        validation_warnings: Optional[List[str]] = None,
        model_used: Optional[str] = None,
        agent_type: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save an agent decision to the database (spec-compliant schema)."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        decision_id = str(uuid.uuid4())

        query = """
        INSERT INTO agent_decisions (
            decision_id, session_id, user_id, symbol, action,
            confidence, opportunity_score, opportunity_tier,
            opportunity_factors, reasoning, strategy_breakdown,
            market_context, tool_calls, validation_status,
            validation_warnings, model_used, agent_type,
            latency_ms, tokens_input, tokens_output
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4, $5,
            $6, $7, $8,
            $9::jsonb, $10, $11::jsonb,
            $12::jsonb, $13::jsonb, $14,
            $15, $16, $17,
            $18, $19, $20
        )
        RETURNING decision_id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                decision_id,
                session_id,
                user_id,
                symbol,
                action,
                confidence,
                opportunity_score,
                opportunity_tier,
                json.dumps(opportunity_factors) if opportunity_factors else None,
                reasoning,
                json.dumps(strategy_breakdown) if strategy_breakdown else None,
                json.dumps(market_context) if market_context else None,
                json.dumps(tool_calls) if tool_calls else None,
                validation_status,
                validation_warnings,
                model_used,
                agent_type,
                latency_ms,
                tokens_input,
                tokens_output,
            )

            return {
                "decision_id": str(row["decision_id"]),
                "saved": True,
            }

    async def save_outcome(
        self,
        decision_id: str,
        actual_return: Optional[float] = None,
        hit_target: Optional[bool] = None,
        exit_price: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        time_to_target_ms: Optional[int] = None,
        recorded_by: str = "outcome-tracker-job",
    ) -> Dict[str, Any]:
        """Save a decision outcome to the decision_outcomes table."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        INSERT INTO decision_outcomes (
            decision_id, actual_return, hit_target, exit_price,
            max_drawdown, time_to_target_ms, recorded_by
        )
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (decision_id) DO UPDATE SET
            actual_return = EXCLUDED.actual_return,
            hit_target = EXCLUDED.hit_target,
            exit_price = EXCLUDED.exit_price,
            max_drawdown = EXCLUDED.max_drawdown,
            time_to_target_ms = EXCLUDED.time_to_target_ms,
            recorded_by = EXCLUDED.recorded_by,
            recorded_at = NOW()
        RETURNING outcome_id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                decision_id,
                actual_return,
                hit_target,
                exit_price,
                max_drawdown,
                time_to_target_ms,
                recorded_by,
            )

            # Also mark on main table
            await conn.execute(
                """
                UPDATE agent_decisions
                SET outcome_recorded = TRUE,
                    actual_return = $2,
                    hit_target = $3
                WHERE decision_id = $1::uuid
                """,
                decision_id,
                actual_return,
                hit_target,
            )

            return {
                "outcome_id": str(row["outcome_id"]),
                "saved": True,
            }

    async def save_feedback(
        self,
        decision_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save user feedback on a decision."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        INSERT INTO decision_feedback (decision_id, user_id, feedback_type, comment)
        VALUES ($1::uuid, $2::uuid, $3, $4)
        RETURNING feedback_id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query, decision_id, user_id, feedback_type, comment
            )
            return {
                "feedback_id": str(row["feedback_id"]),
                "saved": True,
            }

    async def get_decision_outcomes(
        self,
        symbol: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get decision outcomes for accuracy tracking."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = [f"d.created_at >= NOW() - INTERVAL '{days} days'"]
        params: List[Any] = []
        param_idx = 1

        if symbol:
            conditions.append(f"d.symbol = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            d.symbol,
            d.action,
            COUNT(*) as total_decisions,
            COUNT(*) FILTER (WHERE o.hit_target = TRUE) as correct_decisions,
            AVG(o.actual_return) as avg_return,
            AVG(o.max_drawdown) as avg_drawdown
        FROM agent_decisions d
        JOIN decision_outcomes o ON d.decision_id = o.decision_id
        {where_clause}
        GROUP BY d.symbol, d.action
        ORDER BY COUNT(*) FILTER (
            WHERE o.hit_target = TRUE
        )::float / GREATEST(COUNT(*), 1) DESC
        LIMIT ${param_idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            total = row["total_decisions"]
            correct = row["correct_decisions"]
            items.append(
                {
                    "symbol": row["symbol"],
                    "action": row["action"],
                    "total_decisions": total,
                    "correct_decisions": correct,
                    "accuracy": correct / total if total > 0 else 0,
                    "avg_return": (
                        float(row["avg_return"]) if row["avg_return"] else None
                    ),
                    "avg_drawdown": (
                        float(row["avg_drawdown"]) if row["avg_drawdown"] else None
                    ),
                }
            )

        return {"items": items, "period_days": days}
