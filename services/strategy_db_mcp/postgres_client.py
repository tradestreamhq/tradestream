"""
PostgreSQL client for the strategy database MCP server.
Handles connection management and queries against strategy_specs and
strategy_implementations tables for the Learning Agent.
"""

import json
import logging
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
    """Async PostgreSQL client for strategy database MCP queries."""

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
                    "application_name": "strategy_db_mcp",
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

    async def get_top_specs(
        self,
        limit: int = 10,
        offset: int = 0,
        source: str = "ALL",
    ) -> Dict[str, Any]:
        """Get top performing strategy specs ranked by average Sharpe ratio."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        source_filter = ""
        params: List[Any] = []
        param_idx = 1

        if source != "ALL":
            source_filter = f"WHERE ss.source = ${param_idx}"
            params.append(source)
            param_idx += 1

        query = f"""
        SELECT
            ss.id AS spec_id,
            ss.name,
            ss.indicators,
            COALESCE(AVG(
                (si.backtest_metrics->>'sharpe_ratio')::double precision
            ), 0) AS avg_sharpe,
            COUNT(si.id) AS implementations_count
        FROM strategy_specs ss
        LEFT JOIN strategy_implementations si ON si.spec_id = ss.id
        {source_filter}
        GROUP BY ss.id, ss.name, ss.indicators
        ORDER BY avg_sharpe DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        count_query = f"""
        SELECT COUNT(DISTINCT ss.id) FROM strategy_specs ss {source_filter}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[: param_idx - 1])

        items = []
        for row in rows:
            indicators = row["indicators"]
            if isinstance(indicators, str):
                indicators = json.loads(indicators)

            items.append(
                {
                    "spec_id": str(row["spec_id"]),
                    "name": row["name"],
                    "indicators": indicators,
                    "avg_sharpe": float(row["avg_sharpe"]),
                    "implementations_count": row["implementations_count"],
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

    async def get_implementations(
        self,
        spec_id: str,
        status: str = "VALIDATED",
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get implementations for a strategy spec."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        status_filter = ""
        params: List[Any] = [spec_id]
        param_idx = 2

        if status != "ALL":
            status_filter = f"AND si.status = ${param_idx}"
            params.append(status)
            param_idx += 1

        query = f"""
        SELECT
            si.id AS impl_id,
            si.parameters,
            s.symbol,
            COALESCE((si.backtest_metrics->>'sharpe_ratio')::double precision, 0) AS forward_sharpe,
            COALESCE((si.backtest_metrics->>'win_rate')::double precision, 0) AS forward_accuracy,
            si.status
        FROM strategy_implementations si
        JOIN strategy_specs ss ON si.spec_id = ss.id
        LEFT JOIN Strategies s ON s.strategy_type = ss.name
        WHERE si.spec_id = $1::uuid {status_filter}
        ORDER BY forward_sharpe DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        count_query = f"""
        SELECT COUNT(*) FROM strategy_implementations si
        WHERE si.spec_id = $1::uuid {status_filter}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            count_params = [spec_id]
            if status != "ALL":
                count_params.append(status)
            total = await conn.fetchval(count_query, *count_params)

        items = []
        for row in rows:
            parameters = row["parameters"]
            if isinstance(parameters, str):
                parameters = json.loads(parameters)

            items.append(
                {
                    "impl_id": str(row["impl_id"]),
                    "parameters": parameters,
                    "symbol": row["symbol"],
                    "forward_sharpe": float(row["forward_sharpe"]),
                    "forward_accuracy": float(row["forward_accuracy"]),
                    "status": row["status"],
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

    async def submit_new_spec(
        self,
        name: str,
        indicators: Any,
        entry_conditions: Any,
        exit_conditions: Any,
        parameters: Any,
        description: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a new strategy spec generated by the Learning Agent."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        # Check for duplicate name
        check_query = "SELECT id FROM strategy_specs WHERE name = $1"

        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(check_query, name)
            if existing:
                return {
                    "spec_id": str(existing["id"]),
                    "created": False,
                    "validation_errors": [f"A spec with name '{name}' already exists"],
                }

            indicators_json = (
                json.dumps(indicators)
                if not isinstance(indicators, str)
                else indicators
            )
            entry_json = (
                json.dumps(entry_conditions)
                if not isinstance(entry_conditions, str)
                else entry_conditions
            )
            exit_json = (
                json.dumps(exit_conditions)
                if not isinstance(exit_conditions, str)
                else exit_conditions
            )
            params_json = (
                json.dumps(parameters)
                if not isinstance(parameters, str)
                else parameters
            )

            desc = description or reasoning or ""

            query = """
            INSERT INTO strategy_specs (name, indicators, entry_conditions,
                                       exit_conditions, parameters, description, source)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6, 'LLM_GENERATED')
            RETURNING id
            """

            row = await conn.fetchrow(
                query,
                name,
                indicators_json,
                entry_json,
                exit_json,
                params_json,
                desc,
            )

            return {
                "spec_id": str(row["id"]),
                "created": True,
                "validation_errors": [],
            }
