"""
PostgreSQL client for the strategy consumer service.
Handles connection management and strategy insertion with upsert logic.
"""

import asyncio
import json
import logging
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

    async def ensure_table_exists(self) -> None:
        """Ensure the Strategies table exists with proper schema."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS Strategies (
            strategy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            symbol VARCHAR NOT NULL,
            strategy_type VARCHAR NOT NULL,
            parameters JSONB NOT NULL,
            first_discovered_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_evaluated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            current_score DOUBLE PRECISION NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            strategy_hash VARCHAR UNIQUE NOT NULL,
            discovery_symbol VARCHAR,
            discovery_start_time TIMESTAMP,
            discovery_end_time TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        
        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_strategies_symbol ON Strategies(symbol);
        CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON Strategies(strategy_type);
        CREATE INDEX IF NOT EXISTS idx_strategies_current_score ON Strategies(current_score);
        CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON Strategies(is_active);
        CREATE INDEX IF NOT EXISTS idx_strategies_discovery_symbol ON Strategies(discovery_symbol);
        CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON Strategies(created_at);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)
            logging.info("Strategies table schema verified/created")

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

                        if strategy.get("discovery_end_time"):
                            discovery_end_time = datetime.fromisoformat(
                                strategy["discovery_end_time"].replace("Z", "+00:00")
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
