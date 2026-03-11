"""
PostgreSQL client for the strategy consumer service.
Handles connection management and strategy insertion with upsert logic.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import asyncpg
from absl import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Define retry parameters for PostgreSQL operations
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
    """Async PostgreSQL client for strategy storage."""

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
                    "application_name": "strategy_consumer",
                },
            )

            # Test the connection
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

    async def verify_schema(self) -> None:
        """Verify that required tables exist (managed by Alembic migrations)."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'strategies'"
            )
            if result == 0:
                raise RuntimeError(
                    "Strategies table not found. Run database migrations first: "
                    "python -m database.alembic.run_migrations"
                )
            logging.info("Database schema verified")

    async def ensure_or_get_spec(self, strategy_type: str, conn=None) -> uuid.UUID:
        """
        Look up or create a strategy_specs row for the given strategy type.
        Uses upsert to handle concurrency safely.

        Args:
            strategy_type: The strategy type name (e.g., "MACD_CROSSOVER")
            conn: Optional existing connection to reuse

        Returns:
            The UUID of the strategy spec
        """
        upsert_sql = """
        INSERT INTO strategy_specs (name, indicators, entry_conditions, exit_conditions, parameters, source)
        VALUES ($1, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, 'MIGRATED')
        ON CONFLICT (name) DO NOTHING
        """
        select_sql = "SELECT id FROM strategy_specs WHERE name = $1"

        async def _execute(c):
            await c.execute(upsert_sql, strategy_type)
            row = await c.fetchrow(select_sql, strategy_type)
            return row["id"]

        if conn:
            return await _execute(conn)

        async with self.pool.acquire() as c:
            return await _execute(c)

    async def insert_implementation(
        self,
        spec_id: uuid.UUID,
        parameters: dict,
        score: float,
        symbol: str,
        start_time,
        end_time,
        conn=None,
    ) -> uuid.UUID:
        """
        Insert a strategy implementation row linked to a spec.

        Returns:
            The UUID of the new implementation row
        """
        backtest_metrics = {
            "score": score,
            "symbol": symbol,
            "discovery_start": start_time.isoformat() if start_time else None,
            "discovery_end": end_time.isoformat() if end_time else None,
        }

        insert_sql = """
        INSERT INTO strategy_implementations (spec_id, parameters, discovered_by, backtest_metrics, status)
        VALUES ($1, $2, 'GA', $3, 'CANDIDATE')
        RETURNING id
        """

        async def _execute(c):
            row = await c.fetchrow(
                insert_sql,
                spec_id,
                json.dumps(parameters),
                json.dumps(backtest_metrics),
            )
            return row["id"]

        if conn:
            return await _execute(conn)

        async with self.pool.acquire() as c:
            return await _execute(c)

    async def insert_strategies(self, strategies: List[dict]) -> int:
        """
        Insert or update strategies in the database.

        Args:
            strategies: List of strategy dictionaries

        Returns:
            Number of strategies processed
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        if not strategies:
            return 0

        # Prepare the upsert SQL
        upsert_sql = """
        INSERT INTO Strategies (
            symbol, strategy_type, parameters, current_score, strategy_hash,
            discovery_symbol, discovery_start_time, discovery_end_time
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (strategy_hash) DO UPDATE SET
            current_score = EXCLUDED.current_score,
            last_evaluated_at = NOW(),
            updated_at = NOW()
        """

        processed_count = 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for strategy in strategies:
                    try:
                        # Extract values from strategy dict
                        symbol = strategy.get("symbol", "")
                        strategy_type = strategy.get("strategy_type", "")
                        parameters = strategy.get("parameters", {})
                        current_score = strategy.get("current_score", 0.0)
                        strategy_hash = strategy.get("strategy_hash", "")
                        discovery_symbol = strategy.get("discovery_symbol", "")

                        # Parse timestamps
                        discovery_start_time = None
                        discovery_end_time = None

                        if strategy.get("discovery_start_time"):
                            discovery_start_time = datetime.fromisoformat(
                                strategy["discovery_start_time"].replace("Z", "+00:00")
                            )
                            # Convert to timezone-naive datetime for PostgreSQL
                            if discovery_start_time.tzinfo is not None:
                                discovery_start_time = discovery_start_time.replace(
                                    tzinfo=None
                                )

                        if strategy.get("discovery_end_time"):
                            discovery_end_time = datetime.fromisoformat(
                                strategy["discovery_end_time"].replace("Z", "+00:00")
                            )
                            # Convert to timezone-naive datetime for PostgreSQL
                            if discovery_end_time.tzinfo is not None:
                                discovery_end_time = discovery_end_time.replace(
                                    tzinfo=None
                                )

                        # Execute the upsert
                        await conn.execute(
                            upsert_sql,
                            symbol,
                            strategy_type,
                            json.dumps(parameters),
                            current_score,
                            strategy_hash,
                            discovery_symbol,
                            discovery_start_time,
                            discovery_end_time,
                        )

                        processed_count += 1

                        # Write to V2 model (graceful degradation)
                        try:
                            spec_id = await self.ensure_or_get_spec(
                                strategy_type, conn=conn
                            )
                            await self.insert_implementation(
                                spec_id=spec_id,
                                parameters=parameters,
                                score=current_score,
                                symbol=symbol,
                                start_time=discovery_start_time,
                                end_time=discovery_end_time,
                                conn=conn,
                            )
                        except Exception as v2_err:
                            logging.error(
                                f"Failed to write V2 model for {strategy_type}: {v2_err}"
                            )

                    except Exception as e:
                        logging.error(
                            f"Failed to insert strategy {strategy.get('symbol', 'unknown')}: {e}"
                        )
                        # Continue with other strategies instead of failing the entire batch
                        continue

        logging.info(f"Successfully processed {processed_count} strategies")
        return processed_count

    async def get_strategy_count(self) -> int:
        """Get the total number of strategies in the database."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("SELECT COUNT(*) FROM Strategies")
            return result or 0

    async def get_strategies_by_symbol(self, symbol: str) -> List[dict]:
        """Get all strategies for a specific symbol."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT symbol, strategy_type, parameters, current_score, strategy_hash,
               discovery_symbol, discovery_start_time, discovery_end_time,
               first_discovered_at, last_evaluated_at
        FROM Strategies 
        WHERE symbol = $1 AND is_active = TRUE
        ORDER BY current_score DESC
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol)

            strategies = []
            for row in rows:
                strategy = {
                    "symbol": row["symbol"],
                    "strategy_type": row["strategy_type"],
                    "parameters": (
                        json.loads(row["parameters"]) if row["parameters"] else {}
                    ),
                    "current_score": row["current_score"],
                    "strategy_hash": row["strategy_hash"],
                    "discovery_symbol": row["discovery_symbol"],
                    "discovery_start_time": (
                        row["discovery_start_time"].isoformat()
                        if row["discovery_start_time"]
                        else None
                    ),
                    "discovery_end_time": (
                        row["discovery_end_time"].isoformat()
                        if row["discovery_end_time"]
                        else None
                    ),
                    "first_discovered_at": (
                        row["first_discovered_at"].isoformat()
                        if row["first_discovered_at"]
                        else None
                    ),
                    "last_evaluated_at": (
                        row["last_evaluated_at"].isoformat()
                        if row["last_evaluated_at"]
                        else None
                    ),
                }
                strategies.append(strategy)

            return strategies
