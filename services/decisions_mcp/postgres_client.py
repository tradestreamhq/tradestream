"""
PostgreSQL client for the decisions MCP server.
Handles connection management and decision queries against the agent_decisions table.
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
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get recent agent decisions with optional filters."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = []
        params: List[Any] = []
        param_idx = 1

        if symbol:
            conditions.append(f"symbol = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        if action:
            conditions.append(f"action = ${param_idx}")
            params.append(action)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT id, symbol, action, confidence, opportunity_score,
               reasoning, tool_calls, created_at
        FROM agent_decisions
        {where_clause}
        ORDER BY created_at DESC
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
                    "decision_id": str(row["id"]),
                    "symbol": row["symbol"],
                    "action": row["action"],
                    "confidence": float(row["confidence"]),
                    "opportunity_score": (
                        float(row["opportunity_score"])
                        if row["opportunity_score"]
                        else None
                    ),
                    "reasoning": row["reasoning"],
                    "tool_calls": tool_calls,
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
        tool_calls: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Save an agent decision to the database."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        decision_id = str(uuid.uuid4())
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None

        query = """
        INSERT INTO agent_decisions (id, symbol, action, confidence, opportunity_score,
                                     reasoning, tool_calls)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb)
        RETURNING id
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                decision_id,
                symbol,
                action,
                confidence,
                opportunity_score,
                reasoning,
                tool_calls_json,
            )

            return {
                "decision_id": str(row["id"]),
                "saved": True,
            }
