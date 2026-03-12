"""PostgreSQL client for the portfolio state awareness service."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from absl import logging


class PostgresClient:
    """Async PostgreSQL client for reading portfolio state."""

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
            server_settings={"application_name": "portfolio_state"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logging.info("Successfully connected to PostgreSQL")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from paper_portfolio."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
                FROM paper_portfolio
                WHERE quantity > 0
                ORDER BY symbol
                """
            )
            return [
                {
                    "symbol": row["symbol"],
                    "quantity": float(row["quantity"]),
                    "avg_entry_price": float(row["avg_entry_price"]),
                    "unrealized_pnl": float(row["unrealized_pnl"]),
                    "updated_at": row["updated_at"].isoformat(),
                }
                for row in rows
            ]

    async def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades with entry details."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, signal_id, symbol, side, entry_price, quantity, opened_at
                FROM paper_trades
                WHERE status = 'OPEN'
                ORDER BY opened_at DESC
                """
            )
            return [
                {
                    "trade_id": str(row["id"]),
                    "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "entry_price": float(row["entry_price"]),
                    "quantity": float(row["quantity"]),
                    "opened_at": row["opened_at"].isoformat(),
                }
                for row in rows
            ]

    async def get_recent_closed_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recently closed trades for activity history."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, symbol, side, entry_price, exit_price,
                       quantity, pnl, opened_at, closed_at
                FROM paper_trades
                WHERE status = 'CLOSED'
                ORDER BY closed_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [
                {
                    "trade_id": str(row["id"]),
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "entry_price": float(row["entry_price"]),
                    "exit_price": (
                        float(row["exit_price"]) if row["exit_price"] else None
                    ),
                    "quantity": float(row["quantity"]),
                    "pnl": float(row["pnl"]) if row["pnl"] else 0.0,
                    "opened_at": row["opened_at"].isoformat(),
                    "closed_at": (
                        row["closed_at"].isoformat() if row["closed_at"] else None
                    ),
                }
                for row in rows
            ]

    async def get_realized_pnl_today(self) -> float:
        """Get total realized P&L from trades closed today."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pnl), 0) AS today_pnl
                FROM paper_trades
                WHERE status = 'CLOSED'
                  AND closed_at >= CURRENT_DATE
                """
            )
            return float(row["today_pnl"])

    async def get_total_realized_pnl(self) -> float:
        """Get total realized P&L from all closed trades."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pnl), 0) AS total_pnl
                FROM paper_trades
                WHERE status = 'CLOSED'
                """
            )
            return float(row["total_pnl"])
