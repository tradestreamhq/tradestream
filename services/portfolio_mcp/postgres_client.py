"""
PostgreSQL client for the portfolio MCP server.
Handles connection management and portfolio queries against positions and
account tables.
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
    """Async PostgreSQL client for portfolio MCP queries."""

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
                    "application_name": "portfolio_mcp",
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

    async def get_positions(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get current open positions with optional symbol filter."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        if symbol:
            query = """
            SELECT symbol, side, size, entry_price, current_price,
                   unrealized_pnl, opened_at
            FROM positions
            WHERE status = 'OPEN' AND symbol = $1
            ORDER BY opened_at DESC
            LIMIT $2 OFFSET $3
            """
            count_query = """
            SELECT COUNT(*) FROM positions
            WHERE status = 'OPEN' AND symbol = $1
            """
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, symbol, limit, offset)
                total = await conn.fetchval(count_query, symbol)
        else:
            query = """
            SELECT symbol, side, size, entry_price, current_price,
                   unrealized_pnl, opened_at
            FROM positions
            WHERE status = 'OPEN'
            ORDER BY opened_at DESC
            LIMIT $1 OFFSET $2
            """
            count_query = """
            SELECT COUNT(*) FROM positions WHERE status = 'OPEN'
            """
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, limit, offset)
                total = await conn.fetchval(count_query)

        items = []
        for row in rows:
            items.append(
                {
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "size": float(row["size"]),
                    "entry_price": float(row["entry_price"]),
                    "current_price": float(row["current_price"]),
                    "unrealized_pnl": float(row["unrealized_pnl"]),
                    "opened_at": str(row["opened_at"]),
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

    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance and available margin."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        query = """
        SELECT total_balance, available_balance, margin_used, unrealized_pnl
        FROM account_balance
        ORDER BY updated_at DESC
        LIMIT 1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query)
            if not row:
                return {
                    "total_balance": 0.0,
                    "available_balance": 0.0,
                    "margin_used": 0.0,
                    "unrealized_pnl": 0.0,
                }

            return {
                "total_balance": float(row["total_balance"]),
                "available_balance": float(row["available_balance"]),
                "margin_used": float(row["margin_used"]),
                "unrealized_pnl": float(row["unrealized_pnl"]),
            }

    async def validate_trade(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate a proposed trade against risk rules."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        # Get current balance
        balance = await self.get_balance()
        available = balance["available_balance"]

        # Get existing position for the symbol
        position_query = """
        SELECT side, size FROM positions
        WHERE status = 'OPEN' AND symbol = $1
        LIMIT 1
        """

        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(position_query, symbol)

        # Risk validation rules
        max_position_pct = 0.1  # Max 10% of balance per position
        max_size = available * max_position_pct / (price or 1.0) if price else available * max_position_pct

        reasons = []
        valid = True

        if size <= 0:
            valid = False
            reasons.append("Trade size must be positive")

        if price and price * size > available:
            valid = False
            reasons.append("Insufficient available balance")

        if size > max_size and max_size > 0:
            valid = False
            reasons.append(f"Size exceeds max allowed ({max_size:.4f})")

        # Calculate risk score (0-1, higher = riskier)
        risk_score = min(1.0, (price or 1.0) * size / available) if available > 0 else 1.0

        return {
            "valid": valid,
            "reason": "; ".join(reasons) if reasons else "Trade passes all risk checks",
            "max_size": max_size,
            "risk_score": risk_score,
        }
