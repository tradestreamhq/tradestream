"""PostgreSQL client for the position management service."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from absl import logging


class PostgresClient:
    """Async PostgreSQL client for managed position storage."""

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
            server_settings={"application_name": "position_management"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logging.info("Successfully connected to PostgreSQL")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    async def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        strategy_name: Optional[str] = None,
        asset_class: str = "Other",
        signal_id: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a new managed position."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO managed_positions
                    (symbol, side, quantity, filled_quantity, entry_price,
                     current_price, unrealized_pnl, realized_pnl, status,
                     strategy_name, asset_class, signal_id, stop_loss, take_profit)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id, opened_at, updated_at
                """,
                symbol,
                side,
                Decimal(str(quantity)),
                Decimal(str(quantity)),
                Decimal(str(entry_price)),
                Decimal(str(entry_price)),
                Decimal("0"),
                Decimal("0"),
                "FILLED",
                strategy_name,
                asset_class,
                signal_id,
                Decimal(str(stop_loss)) if stop_loss is not None else None,
                Decimal(str(take_profit)) if take_profit is not None else None,
            )

            return {
                "id": str(row["id"]),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "filled_quantity": quantity,
                "entry_price": entry_price,
                "current_price": entry_price,
                "status": "FILLED",
                "strategy_name": strategy_name,
                "asset_class": asset_class,
                "opened_at": row["opened_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
            }

    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        close_quantity: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Close or partially close a managed position."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            pos = await conn.fetchrow(
                """
                SELECT id, symbol, side, quantity, filled_quantity,
                       entry_price, realized_pnl
                FROM managed_positions
                WHERE id = $1 AND status != 'CLOSED'
                """,
                position_id,
            )
            if not pos:
                return None

            filled = float(pos["filled_quantity"])
            qty = min(close_quantity or filled, filled)
            entry = float(pos["entry_price"])

            if pos["side"] == "LONG":
                pnl = (exit_price - entry) * qty
            else:
                pnl = (entry - exit_price) * qty

            remaining = filled - qty
            total_realized = float(pos["realized_pnl"]) + pnl
            total_qty = float(pos["quantity"])
            closed_qty = total_qty - remaining

            if closed_qty >= total_qty:
                new_status = "CLOSED"
            elif closed_qty > 0:
                new_status = "PARTIALLY_CLOSED"
            else:
                new_status = "FILLED"

            unrealized = 0.0
            if remaining > 0:
                if pos["side"] == "LONG":
                    unrealized = remaining * (exit_price - entry)
                else:
                    unrealized = remaining * (entry - exit_price)

            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE managed_positions
                    SET filled_quantity = $1,
                        current_price = $2,
                        unrealized_pnl = $3,
                        realized_pnl = $4,
                        status = $5,
                        exit_price = CASE WHEN $5 = 'CLOSED' THEN $2 ELSE exit_price END,
                        closed_at = CASE WHEN $5 = 'CLOSED' THEN NOW() ELSE closed_at END,
                        updated_at = NOW()
                    WHERE id = $6
                    """,
                    Decimal(str(remaining)),
                    Decimal(str(exit_price)),
                    Decimal(str(round(unrealized, 8))),
                    Decimal(str(round(total_realized, 8))),
                    new_status,
                    position_id,
                )

            return {
                "id": str(pos["id"]),
                "symbol": pos["symbol"],
                "side": pos["side"],
                "entry_price": entry,
                "exit_price": exit_price,
                "closed_quantity": qty,
                "remaining_quantity": remaining,
                "realized_pnl": round(pnl, 8),
                "total_realized_pnl": round(total_realized, 8),
                "status": new_status,
            }

    async def update_market_price(
        self, position_id: str, current_price: float
    ) -> None:
        """Update the current market price and unrealized P&L for a position."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE managed_positions
                SET current_price = $1,
                    unrealized_pnl = CASE
                        WHEN side = 'LONG' THEN filled_quantity * ($1 - entry_price)
                        ELSE filled_quantity * (entry_price - $1)
                    END,
                    updated_at = NOW()
                WHERE id = $2 AND status != 'CLOSED'
                """,
                Decimal(str(current_price)),
                position_id,
            )

    async def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get a single position by ID."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, symbol, side, quantity, filled_quantity, entry_price,
                       current_price, unrealized_pnl, realized_pnl, status,
                       strategy_name, asset_class, signal_id, stop_loss, take_profit,
                       opened_at, updated_at, closed_at, exit_price
                FROM managed_positions
                WHERE id = $1
                """,
                position_id,
            )
            if not row:
                return None
            return _row_to_dict(row)

    async def get_positions(
        self,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        status: Optional[str] = None,
        asset_class: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query positions with optional filters."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = []
        params = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        if strategy_name:
            conditions.append(f"strategy_name = ${idx}")
            params.append(strategy_name)
            idx += 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        if asset_class:
            conditions.append(f"asset_class = ${idx}")
            params.append(asset_class)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT id, symbol, side, quantity, filled_quantity, entry_price,
               current_price, unrealized_pnl, realized_pnl, status,
               strategy_name, asset_class, signal_id, stop_loss, take_profit,
               opened_at, updated_at, closed_at, exit_price
        FROM managed_positions
        {where}
        ORDER BY opened_at DESC
        LIMIT ${idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [_row_to_dict(row) for row in rows]

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all non-closed positions."""
        return await self.get_positions(status=None, limit=1000)

    async def get_position_summary(
        self, group_by: str = "strategy"
    ) -> List[Dict[str, Any]]:
        """Get aggregated position stats grouped by strategy or asset class."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        group_col = (
            "strategy_name" if group_by == "strategy" else "asset_class"
        )

        query = f"""
        SELECT
            COALESCE({group_col}, 'unknown') AS group_key,
            COUNT(*) FILTER (WHERE status != 'CLOSED') AS num_open,
            COUNT(*) FILTER (WHERE status = 'CLOSED') AS num_closed,
            COALESCE(SUM(unrealized_pnl) FILTER (WHERE status != 'CLOSED'), 0)
                AS total_unrealized_pnl,
            COALESCE(SUM(realized_pnl), 0) AS total_realized_pnl,
            COALESCE(SUM(filled_quantity * current_price)
                FILTER (WHERE status != 'CLOSED'), 0) AS total_exposure
        FROM managed_positions
        GROUP BY {group_col}
        ORDER BY {group_col}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [
                {
                    "group_key": row["group_key"],
                    "num_open": row["num_open"],
                    "num_closed": row["num_closed"],
                    "total_unrealized_pnl": float(row["total_unrealized_pnl"]),
                    "total_realized_pnl": float(row["total_realized_pnl"]),
                    "total_exposure": float(row["total_exposure"]),
                }
                for row in rows
            ]


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a database row to a position dict."""
    return {
        "id": str(row["id"]),
        "symbol": row["symbol"],
        "side": row["side"],
        "quantity": float(row["quantity"]),
        "filled_quantity": float(row["filled_quantity"]),
        "entry_price": float(row["entry_price"]),
        "current_price": float(row["current_price"]),
        "unrealized_pnl": float(row["unrealized_pnl"]),
        "realized_pnl": float(row["realized_pnl"]),
        "status": row["status"],
        "strategy_name": row["strategy_name"],
        "asset_class": row["asset_class"],
        "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
        "stop_loss": float(row["stop_loss"]) if row["stop_loss"] is not None else None,
        "take_profit": (
            float(row["take_profit"]) if row["take_profit"] is not None else None
        ),
        "opened_at": row["opened_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
        "exit_price": (
            float(row["exit_price"]) if row["exit_price"] is not None else None
        ),
    }
