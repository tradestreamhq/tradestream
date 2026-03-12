"""PostgreSQL client for the strategy monitor MCP server.

Wraps the same database queries used by the strategy_monitor_api REST service,
providing async access to strategy monitoring data.
"""

import logging
from typing import Any

import asyncpg
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class PostgresClient:
    """Async PostgreSQL client for strategy monitoring queries."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
    ) -> None:
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._password = password
        self._pool: asyncpg.Pool | None = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def connect(self) -> None:
        """Create a connection pool."""
        self._pool = await asyncpg.create_pool(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
            min_size=2,
            max_size=10,
        )
        logger.info("Connected to PostgreSQL at %s:%d", self._host, self._port)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()

    async def get_strategies(
        self,
        symbol: str | None = None,
        strategy_type: str | None = None,
        min_score: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Fetch strategies with optional filtering and pagination."""
        query_parts = ["SELECT * FROM strategy_implementations WHERE 1=1"]
        count_parts = [
            "SELECT COUNT(*) FROM strategy_implementations WHERE 1=1"
        ]
        params: list[Any] = []
        idx = 1

        if symbol:
            query_parts.append(f"AND symbol = ${idx}")
            count_parts.append(f"AND symbol = ${idx}")
            params.append(symbol)
            idx += 1

        if strategy_type:
            query_parts.append(f"AND strategy_type = ${idx}")
            count_parts.append(f"AND strategy_type = ${idx}")
            params.append(strategy_type)
            idx += 1

        if min_score is not None:
            query_parts.append(f"AND current_score >= ${idx}")
            count_parts.append(f"AND current_score >= ${idx}")
            params.append(min_score)
            idx += 1

        query_parts.append("ORDER BY current_score DESC NULLS LAST")
        query_parts.append(f"LIMIT ${idx} OFFSET ${idx + 1}")
        params_with_pagination = params + [limit, offset]

        query = " ".join(query_parts)
        count_query = " ".join(count_parts)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params_with_pagination)
            total = await conn.fetchval(count_query, *params)

        strategies = [dict(row) for row in rows]
        return {
            "strategies": strategies,
            "count": len(strategies),
            "total_count": total or 0,
            "limit": limit,
            "offset": offset,
        }

    async def get_strategy_by_id(
        self, strategy_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single strategy by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM strategy_implementations WHERE id = $1",
                strategy_id,
            )
        if row is None:
            return None
        return dict(row)

    async def get_metrics(self) -> dict[str, Any]:
        """Fetch aggregated strategy metrics."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM strategy_implementations"
            )
            avg_score = await conn.fetchval(
                "SELECT AVG(current_score) FROM strategy_implementations"
            )
            by_type = await conn.fetch(
                "SELECT strategy_type, COUNT(*) as count, "
                "AVG(current_score) as avg_score "
                "FROM strategy_implementations "
                "GROUP BY strategy_type ORDER BY count DESC"
            )
        return {
            "total_strategies": total or 0,
            "avg_score": float(avg_score) if avg_score else 0.0,
            "by_type": [dict(row) for row in by_type],
        }

    async def get_symbols(self) -> list[str]:
        """Fetch distinct trading symbols."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT symbol FROM strategy_implementations "
                "ORDER BY symbol"
            )
        return [row["symbol"] for row in rows]

    async def get_strategy_types(self) -> list[str]:
        """Fetch distinct strategy types."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT strategy_type FROM strategy_implementations "
                "ORDER BY strategy_type"
            )
        return [row["strategy_type"] for row in rows]
