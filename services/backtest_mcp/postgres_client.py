"""
PostgreSQL client for the backtest MCP server.
Handles connection management and backtest queries against strategy_implementations
and backtest_results tables.
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
    """Async PostgreSQL client for backtest MCP queries."""

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
                    "application_name": "backtest_mcp",
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

    async def run_backtest(
        self,
        strategy_id: str,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a backtest by looking up existing backtest results or triggering a new one.

        For now, queries the most recent backtest results for the given strategy
        and symbol combination.
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT
            si.id AS impl_id,
            si.backtest_metrics,
            si.created_at
        FROM strategy_implementations si
        JOIN strategy_specs ss ON si.spec_id = ss.id
        JOIN Strategies s ON s.strategy_type = ss.name
        WHERE si.id = $1::uuid
          AND s.symbol = $2
        ORDER BY si.created_at DESC
        LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, strategy_id, symbol)
            if not row:
                return {
                    "error": "No backtest results found for this strategy and symbol"
                }

            metrics = row["backtest_metrics"] or {}
            if isinstance(metrics, str):
                metrics = json.loads(metrics)

            return {
                "impl_id": str(row["impl_id"]),
                "total_return": metrics.get("total_return", 0.0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "win_rate": metrics.get("win_rate", 0.0),
                "trades": metrics.get("total_trades", 0),
            }

    async def get_historical_performance(
        self,
        strategy_id: str,
        symbol: Optional[str] = None,
        period: str = "3m",
    ) -> Dict[str, Any]:
        """Get historical performance metrics for a strategy implementation."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        period_map = {
            "1w": "7 days",
            "1m": "30 days",
            "3m": "90 days",
            "6m": "180 days",
            "1y": "365 days",
        }
        interval = period_map.get(period, "90 days")

        query = """
        SELECT
            si.id AS impl_id,
            si.backtest_metrics,
            si.paper_metrics,
            si.live_metrics,
            si.created_at
        FROM strategy_implementations si
        WHERE si.id = $1::uuid
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, strategy_id)
            if not row:
                return {"error": "Strategy implementation not found"}

            # Aggregate metrics from available environments
            all_metrics = {}
            for env in ("backtest", "paper", "live"):
                m = row[f"{env}_metrics"]
                if m:
                    if isinstance(m, str):
                        m = json.loads(m)
                    all_metrics[env] = m

            # Use best available metrics
            best = all_metrics.get(
                "live", all_metrics.get("paper", all_metrics.get("backtest", {}))
            )

            return {
                "total_signals": best.get("total_trades", 0),
                "accuracy": best.get("win_rate", 0.0),
                "avg_return": best.get("avg_return", 0.0),
                "sharpe": best.get("sharpe_ratio", 0.0),
                "period": period,
                "environments_available": list(all_metrics.keys()),
            }
