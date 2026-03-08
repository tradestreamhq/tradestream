"""
PostgreSQL client for the signal MCP server.
Handles signal storage and agent decision logging.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from absl import logging


class PostgresClient:
    """Async PostgreSQL client for signal and decision storage."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        logging.info(
            f"Connecting to PostgreSQL at {self.host}:{self.port}/{self.database}"
        )
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
            min_size=1,
            max_size=10,
            command_timeout=60,
            server_settings={"application_name": "signal_mcp"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logging.info("Successfully connected to PostgreSQL")

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    async def insert_signal(
        self,
        symbol: str,
        action: str,
        confidence: float,
        reasoning: str,
        strategy_breakdown: List[Dict[str, Any]],
        price: float = 0.0,
    ) -> str:
        """Insert a signal into the signals table.

        Returns:
            The UUID of the inserted signal.
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        metadata = {
            "reasoning": reasoning,
            "strategy_breakdown": strategy_breakdown,
        }

        query = """
        INSERT INTO signals (instrument, signal_type, strength, price, metadata)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                symbol,
                action,
                confidence,
                Decimal(str(price)),
                json.dumps(metadata),
            )
            signal_id = str(row["id"])
            logging.info(f"Inserted signal {signal_id} for {symbol}")
            return signal_id

    async def insert_decision(
        self,
        signal_id: str,
        score: float,
        tier: str,
        reasoning: str,
        tool_calls: List[Dict[str, Any]],
        model_used: str,
        latency_ms: int,
        tokens_used: int,
    ) -> str:
        """Insert an agent decision into the agent_decisions table.

        Returns:
            The UUID of the inserted decision.
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        INSERT INTO agent_decisions
            (signal_id, score, tier, reasoning, tool_calls,
             model_used, latency_ms, tokens_used)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                signal_id,
                Decimal(str(score)),
                tier,
                reasoning,
                json.dumps(tool_calls),
                model_used,
                latency_ms,
                tokens_used,
            )
            decision_id = str(row["id"])
            logging.info(f"Inserted decision {decision_id}")
            return decision_id

    async def get_recent_signals(
        self,
        symbol: Optional[str] = None,
        limit: int = 20,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent signals, optionally filtered by symbol and min score."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = []
        params = []
        param_idx = 1

        if symbol:
            conditions.append(f"s.instrument = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        if min_score is not None:
            conditions.append(f"d.score >= ${param_idx}")
            params.append(Decimal(str(min_score)))
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            s.id AS signal_id,
            s.instrument AS symbol,
            s.signal_type AS action,
            s.strength AS confidence,
            d.score,
            d.tier,
            s.metadata->>'reasoning' AS reasoning,
            s.created_at AS timestamp
        FROM signals s
        LEFT JOIN agent_decisions d ON d.signal_id = s.id
        {where_clause}
        ORDER BY s.created_at DESC
        LIMIT ${param_idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                {
                    "signal_id": str(row["signal_id"]),
                    "symbol": row["symbol"],
                    "action": row["action"],
                    "confidence": float(row["confidence"]) if row["confidence"] else None,
                    "score": float(row["score"]) if row["score"] else None,
                    "tier": row["tier"],
                    "reasoning": row["reasoning"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                }
                for row in rows
            ]

    async def get_paper_pnl(
        self, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate simulated P&L from signals table."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = ["outcome IS NOT NULL"]
        params = []
        param_idx = 1

        if symbol:
            conditions.append(f"instrument = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            COALESCE(SUM(pnl), 0) AS total_pnl,
            COUNT(*) FILTER (WHERE outcome = 'PROFIT') AS wins,
            COUNT(*) FILTER (WHERE outcome IN ('PROFIT', 'LOSS', 'BREAKEVEN')) AS total_closed,
            COALESCE(AVG(pnl_percent), 0) AS avg_return
        FROM signals
        {where_clause}
        """

        open_conditions = ["outcome IS NULL OR outcome = 'PENDING'"]
        if symbol:
            open_conditions.append(f"instrument = ${param_idx - 1}")

        open_query = f"""
        SELECT COUNT(*) AS open_count
        FROM signals
        WHERE {" AND ".join(open_conditions)}
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            open_row = await conn.fetchrow(open_query, *params)

            total_closed = row["total_closed"] or 0
            wins = row["wins"] or 0
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0

            return {
                "total_pnl": float(row["total_pnl"]),
                "win_rate": round(win_rate, 2),
                "avg_return": float(row["avg_return"]),
                "open_positions": open_row["open_count"] or 0,
            }

    async def get_signal_accuracy(
        self, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Compare signal_type vs outcome for signals in lookback window."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        query = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE
                (signal_type IN ('BUY', 'CLOSE_SHORT') AND outcome = 'PROFIT')
                OR (signal_type IN ('SELL', 'CLOSE_LONG') AND outcome = 'PROFIT')
                OR (signal_type = 'HOLD' AND outcome = 'BREAKEVEN')
            ) AS correct,
            AVG(strength) FILTER (WHERE
                (signal_type IN ('BUY', 'CLOSE_SHORT') AND outcome = 'PROFIT')
                OR (signal_type IN ('SELL', 'CLOSE_LONG') AND outcome = 'PROFIT')
                OR (signal_type = 'HOLD' AND outcome = 'BREAKEVEN')
            ) AS avg_confidence_correct,
            AVG(strength) FILTER (WHERE
                outcome IS NOT NULL
                AND NOT (
                    (signal_type IN ('BUY', 'CLOSE_SHORT') AND outcome = 'PROFIT')
                    OR (signal_type IN ('SELL', 'CLOSE_LONG') AND outcome = 'PROFIT')
                    OR (signal_type = 'HOLD' AND outcome = 'BREAKEVEN')
                )
            ) AS avg_confidence_incorrect
        FROM signals
        WHERE created_at >= $1
            AND outcome IS NOT NULL
            AND outcome != 'PENDING'
            AND outcome != 'CANCELLED'
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, cutoff)

            total = row["total"] or 0
            correct = row["correct"] or 0
            accuracy = (correct / total * 100) if total > 0 else 0.0

            return {
                "total": total,
                "correct": correct,
                "accuracy": round(accuracy, 2),
                "avg_confidence_correct": (
                    float(row["avg_confidence_correct"])
                    if row["avg_confidence_correct"]
                    else None
                ),
                "avg_confidence_incorrect": (
                    float(row["avg_confidence_incorrect"])
                    if row["avg_confidence_incorrect"]
                    else None
                ),
            }
