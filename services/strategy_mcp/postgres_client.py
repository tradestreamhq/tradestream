"""
PostgreSQL client for the strategy MCP server.
Handles connection management and strategy queries against strategy_specs and
strategy_implementations tables.
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
    """Async PostgreSQL client for strategy MCP queries."""

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
                    "application_name": "strategy_mcp",
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

    async def get_top_strategies(
        self,
        symbol: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Query top strategies by Sharpe ratio for a symbol."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT DISTINCT ON (si.id)
            ss.name AS spec_name,
            si.id AS impl_id,
            COALESCE((si.backtest_metrics->>'sharpe_ratio')::double precision, 0) AS score,
            si.parameters,
            ss.name AS strategy_type
        FROM strategy_implementations si
        JOIN strategy_specs ss ON si.spec_id = ss.id
        JOIN Strategies s ON s.strategy_type = ss.name
        WHERE si.status IN ('VALIDATED', 'DEPLOYED')
          AND s.symbol = $1
          AND COALESCE((si.backtest_metrics->>'sharpe_ratio')::double precision, 0) >= $2
        ORDER BY si.id, COALESCE((si.backtest_metrics->>'sharpe_ratio')::double precision, 0) DESC
        """

        # Wrap with outer query to apply proper ORDER BY and LIMIT
        wrapped_query = f"""
        SELECT spec_name, impl_id, score, parameters, strategy_type
        FROM ({query}) sub
        ORDER BY score DESC
        LIMIT $3
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(wrapped_query, symbol, min_score, limit)

            results = []
            for row in rows:
                results.append(
                    {
                        "spec_name": row["spec_name"],
                        "impl_id": str(row["impl_id"]),
                        "score": row["score"],
                        "params": (
                            json.loads(row["parameters"])
                            if isinstance(row["parameters"], str)
                            else row["parameters"]
                        ),
                        "strategy_type": row["strategy_type"],
                    }
                )
            return results

    async def get_spec(self, spec_name: str) -> Optional[Dict[str, Any]]:
        """Get a strategy spec by name."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT name, indicators, entry_conditions, exit_conditions, parameters, source
        FROM strategy_specs
        WHERE name = $1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, spec_name)
            if not row:
                return None

            return {
                "name": row["name"],
                "indicators": row["indicators"],
                "entry_conditions": row["entry_conditions"],
                "exit_conditions": row["exit_conditions"],
                "parameters": row["parameters"],
                "source": row["source"],
            }

    async def get_performance(
        self,
        impl_id: str,
        environment: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get flattened performance metrics for a strategy implementation."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT backtest_metrics, paper_metrics, live_metrics
        FROM strategy_implementations
        WHERE id = $1::uuid
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, impl_id)
            if not row:
                return None

            result = {}
            if environment:
                metrics_key = f"{environment}_metrics"
                metrics = row.get(metrics_key)
                if metrics:
                    result[environment] = metrics
            else:
                for env in ("backtest", "paper", "live"):
                    metrics = row[f"{env}_metrics"]
                    if metrics:
                        result[env] = metrics

            return result

    async def get_performance_batch(
        self,
        impl_ids: List[str],
        environment: Optional[str] = None,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get performance metrics for multiple strategy implementations in one query.

        Args:
            impl_ids: List of strategy implementation UUIDs.
            environment: Optional filter to specific environment.

        Returns:
            Dict mapping impl_id to its performance metrics (or None if not found).
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        if not impl_ids:
            return {}

        query = """
        SELECT id, backtest_metrics, paper_metrics, live_metrics
        FROM strategy_implementations
        WHERE id = ANY($1::uuid[])
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, impl_ids)

            rows_by_id = {str(row["id"]): row for row in rows}

            results = {}
            for impl_id in impl_ids:
                row = rows_by_id.get(impl_id)
                if not row:
                    results[impl_id] = None
                    continue

                metrics = {}
                if environment:
                    metrics_key = f"{environment}_metrics"
                    env_metrics = row.get(metrics_key)
                    if env_metrics:
                        metrics[environment] = env_metrics
                else:
                    for env in ("backtest", "paper", "live"):
                        env_metrics = row[f"{env}_metrics"]
                        if env_metrics:
                            metrics[env] = env_metrics

                results[impl_id] = metrics

            return results

    async def list_strategy_types(self) -> List[str]:
        """Get distinct spec names with VALIDATED or DEPLOYED implementations."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT DISTINCT ss.name
        FROM strategy_specs ss
        JOIN strategy_implementations si ON si.spec_id = ss.id
        WHERE si.status IN ('VALIDATED', 'DEPLOYED')
        ORDER BY ss.name
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row["name"] for row in rows]

    async def create_spec(
        self,
        name: str,
        indicators: Any,
        entry_conditions: Any,
        exit_conditions: Any,
        parameters: Any,
        description: str,
    ) -> Dict[str, str]:
        """Insert a new strategy spec with source=LLM_GENERATED."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        INSERT INTO strategy_specs (name, indicators, entry_conditions, exit_conditions, parameters, description, source)
        VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6, 'LLM_GENERATED')
        RETURNING id
        """

        indicators_json = (
            json.dumps(indicators) if not isinstance(indicators, str) else indicators
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
            json.dumps(parameters) if not isinstance(parameters, str) else parameters
        )

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                name,
                indicators_json,
                entry_json,
                exit_json,
                params_json,
                description,
            )
            return {"spec_id": str(row["id"])}

    async def get_walk_forward(self, impl_id: str) -> Optional[Dict[str, Any]]:
        """Get walk-forward validation results for a strategy implementation.

        Joins strategy_implementations -> Strategies (via spec name matching)
        -> walk_forward_results.
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT
            wfr.validation_status,
            wfr.sharpe_degradation,
            wfr.in_sample_sharpe,
            wfr.out_of_sample_sharpe,
            wfr.window_results
        FROM strategy_implementations si
        JOIN strategy_specs ss ON si.spec_id = ss.id
        JOIN Strategies s ON s.strategy_type = ss.name
        JOIN walk_forward_results wfr ON wfr.strategy_id = s.strategy_id
        WHERE si.id = $1::uuid
        ORDER BY wfr.validated_at DESC
        LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, impl_id)
            if not row:
                return None

            return {
                "validation_status": row["validation_status"],
                "sharpe_degradation": row["sharpe_degradation"],
                "in_sample_sharpe": row["in_sample_sharpe"],
                "out_of_sample_sharpe": row["out_of_sample_sharpe"],
                "window_results": row["window_results"],
            }
