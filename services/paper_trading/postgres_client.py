"""PostgreSQL client for the paper trading service."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from absl import logging


class PostgresClient:
    """Async PostgreSQL client for paper trade and portfolio storage."""

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
            server_settings={"application_name": "paper_trading"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        logging.info("Successfully connected to PostgreSQL")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL connection pool closed")

    async def execute_trade(
        self,
        signal_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
    ) -> Dict[str, Any]:
        """Open a paper trade from a signal and update portfolio."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO paper_trades
                        (signal_id, symbol, side, entry_price, quantity, status)
                    VALUES ($1, $2, $3, $4, $5, 'OPEN')
                    RETURNING id, opened_at
                    """,
                    signal_id,
                    symbol,
                    side,
                    Decimal(str(entry_price)),
                    Decimal(str(quantity)),
                )
                trade_id = str(row["id"])

                # Update portfolio: upsert position
                existing = await conn.fetchrow(
                    "SELECT quantity, avg_entry_price FROM paper_portfolio WHERE symbol = $1",
                    symbol,
                )

                if existing and side == "BUY":
                    old_qty = float(existing["quantity"])
                    old_avg = float(existing["avg_entry_price"])
                    new_qty = old_qty + quantity
                    new_avg = (
                        (old_avg * old_qty + entry_price * quantity) / new_qty
                        if new_qty > 0
                        else 0
                    )
                    await conn.execute(
                        """
                        UPDATE paper_portfolio
                        SET quantity = $1, avg_entry_price = $2, updated_at = NOW()
                        WHERE symbol = $3
                        """,
                        Decimal(str(new_qty)),
                        Decimal(str(new_avg)),
                        symbol,
                    )
                elif existing and side == "SELL":
                    old_qty = float(existing["quantity"])
                    new_qty = old_qty - quantity
                    if new_qty <= 0:
                        await conn.execute(
                            "DELETE FROM paper_portfolio WHERE symbol = $1",
                            symbol,
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE paper_portfolio
                            SET quantity = $1, updated_at = NOW()
                            WHERE symbol = $2
                            """,
                            Decimal(str(new_qty)),
                            symbol,
                        )
                elif side == "BUY":
                    await conn.execute(
                        """
                        INSERT INTO paper_portfolio (symbol, quantity, avg_entry_price)
                        VALUES ($1, $2, $3)
                        """,
                        symbol,
                        Decimal(str(quantity)),
                        Decimal(str(entry_price)),
                    )

                return {
                    "trade_id": trade_id,
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "status": "OPEN",
                    "opened_at": row["opened_at"].isoformat(),
                }

    async def close_trade(
        self, trade_id: str, exit_price: float
    ) -> Optional[Dict[str, Any]]:
        """Close an open paper trade and compute P&L."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            trade = await conn.fetchrow(
                """
                SELECT id, signal_id, symbol, side, entry_price, quantity
                FROM paper_trades
                WHERE id = $1 AND status = 'OPEN'
                """,
                trade_id,
            )
            if not trade:
                return None

            entry = float(trade["entry_price"])
            qty = float(trade["quantity"])
            if trade["side"] == "BUY":
                pnl = (exit_price - entry) * qty
            else:
                pnl = (entry - exit_price) * qty

            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE paper_trades
                    SET exit_price = $1, pnl = $2, closed_at = NOW(), status = 'CLOSED'
                    WHERE id = $3
                    """,
                    Decimal(str(exit_price)),
                    Decimal(str(pnl)),
                    trade_id,
                )

                # Remove from portfolio
                await conn.execute(
                    """
                    UPDATE paper_portfolio
                    SET quantity = quantity - $1, updated_at = NOW()
                    WHERE symbol = $2
                    """,
                    trade["quantity"],
                    trade["symbol"],
                )
                await conn.execute(
                    "DELETE FROM paper_portfolio WHERE symbol = $1 AND quantity <= 0",
                    trade["symbol"],
                )

            return {
                "trade_id": str(trade["id"]),
                "symbol": trade["symbol"],
                "side": trade["side"],
                "entry_price": entry,
                "exit_price": exit_price,
                "quantity": qty,
                "pnl": round(pnl, 8),
                "status": "CLOSED",
            }

    async def get_portfolio(self) -> List[Dict[str, Any]]:
        """Get all current paper portfolio positions."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
                FROM paper_portfolio
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

    async def update_unrealized_pnl(self, symbol: str, current_price: float) -> None:
        """Update unrealized P&L for a portfolio position."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE paper_portfolio
                SET unrealized_pnl = (quantity * ($1 - avg_entry_price)),
                    updated_at = NOW()
                WHERE symbol = $2
                """,
                Decimal(str(current_price)),
                symbol,
            )

    async def get_trades(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get paper trades with optional filters."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = []
        params = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT id, signal_id, symbol, side, entry_price, exit_price,
               quantity, pnl, opened_at, closed_at, status
        FROM paper_trades
        {where}
        ORDER BY opened_at DESC
        LIMIT ${idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                {
                    "trade_id": str(row["id"]),
                    "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "entry_price": float(row["entry_price"]),
                    "exit_price": (
                        float(row["exit_price"]) if row["exit_price"] else None
                    ),
                    "quantity": float(row["quantity"]),
                    "pnl": float(row["pnl"]) if row["pnl"] else None,
                    "opened_at": row["opened_at"].isoformat(),
                    "closed_at": (
                        row["closed_at"].isoformat() if row["closed_at"] else None
                    ),
                    "status": row["status"],
                }
                for row in rows
            ]

    async def get_pnl_summary(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated P&L summary from closed trades."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = ["status = 'CLOSED'"]
        params = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            COALESCE(SUM(pnl), 0) AS total_pnl,
            COUNT(*) AS total_trades,
            COUNT(*) FILTER (WHERE pnl > 0) AS winning_trades,
            COUNT(*) FILTER (WHERE pnl < 0) AS losing_trades,
            COUNT(*) FILTER (WHERE pnl = 0) AS breakeven_trades,
            COALESCE(AVG(pnl), 0) AS avg_pnl,
            COALESCE(MAX(pnl), 0) AS best_trade,
            COALESCE(MIN(pnl), 0) AS worst_trade
        FROM paper_trades
        {where}
        """

        open_query = f"""
        SELECT
            COUNT(*) AS open_count,
            COALESCE(SUM(pp.unrealized_pnl), 0) AS total_unrealized_pnl
        FROM paper_portfolio pp
        {"WHERE pp.symbol = $1" if symbol else ""}
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            open_row = await conn.fetchrow(open_query, *([symbol] if symbol else []))

            total = row["total_trades"] or 0
            wins = row["winning_trades"] or 0
            win_rate = (wins / total * 100) if total > 0 else 0.0

            return {
                "total_pnl": float(row["total_pnl"]),
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": row["losing_trades"] or 0,
                "breakeven_trades": row["breakeven_trades"] or 0,
                "win_rate": round(win_rate, 2),
                "avg_pnl": float(row["avg_pnl"]),
                "best_trade": float(row["best_trade"]),
                "worst_trade": float(row["worst_trade"]),
                "open_positions": open_row["open_count"] or 0,
                "total_unrealized_pnl": float(open_row["total_unrealized_pnl"]),
            }

    async def log_decision(
        self,
        signal_id: str,
        reasoning: str,
        action: str,
    ) -> str:
        """Log a paper trade decision to agent_decisions table."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        tool_calls = [{"tool": "paper_trade_execute", "action": action}]
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_decisions
                    (signal_id, score, tier, reasoning, tool_calls,
                     model_used, latency_ms, tokens_used)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                signal_id,
                Decimal("0"),
                "PAPER_TRADE",
                reasoning,
                json.dumps(tool_calls),
                "paper_trading_service",
                0,
                0,
            )
            return str(row["id"])

    # ---- Session management ----

    async def create_session(self, starting_balance: float) -> Dict[str, Any]:
        """Create a new paper trading session."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO paper_trading_sessions
                    (starting_balance, current_balance)
                VALUES ($1, $1)
                RETURNING id, starting_balance, current_balance, status, started_at
                """,
                Decimal(str(starting_balance)),
            )
            return {
                "session_id": str(row["id"]),
                "starting_balance": float(row["starting_balance"]),
                "current_balance": float(row["current_balance"]),
                "status": row["status"],
                "started_at": row["started_at"].isoformat(),
            }

    async def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Return the currently active session, or None."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, starting_balance, current_balance, status,
                       started_at, total_realized_pnl, total_trades
                FROM paper_trading_sessions
                WHERE status = 'ACTIVE'
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            if not row:
                return None
            return self._session_row_to_dict(row)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, starting_balance, current_balance, status,
                       started_at, stopped_at, total_realized_pnl, total_trades
                FROM paper_trading_sessions
                WHERE id = $1
                """,
                session_id,
            )
            if not row:
                return None
            return self._session_row_to_dict(row)

    async def stop_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Stop an active session."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE paper_trading_sessions
                SET status = 'STOPPED', stopped_at = NOW()
                WHERE id = $1 AND status = 'ACTIVE'
                RETURNING id, starting_balance, current_balance, status,
                          started_at, stopped_at, total_realized_pnl, total_trades
                """,
                session_id,
            )
            if not row:
                return None
            return self._session_row_to_dict(row)

    async def execute_session_trade(
        self,
        session_id: str,
        signal_id: Optional[str],
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
    ) -> Dict[str, Any]:
        """Execute a trade within a session, updating session balance."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        cost = Decimal(str(entry_price)) * Decimal(str(quantity))

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO paper_trades
                        (session_id, signal_id, symbol, side, entry_price, quantity, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'OPEN')
                    RETURNING id, opened_at
                    """,
                    session_id,
                    signal_id,
                    symbol,
                    side,
                    Decimal(str(entry_price)),
                    Decimal(str(quantity)),
                )
                trade_id = str(row["id"])

                # Update session balance and trade count
                if side == "BUY":
                    await conn.execute(
                        """
                        UPDATE paper_trading_sessions
                        SET current_balance = current_balance - $1,
                            total_trades = total_trades + 1
                        WHERE id = $2
                        """,
                        cost,
                        session_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE paper_trading_sessions
                        SET current_balance = current_balance + $1,
                            total_trades = total_trades + 1
                        WHERE id = $2
                        """,
                        cost,
                        session_id,
                    )

                # Update portfolio position
                existing = await conn.fetchrow(
                    "SELECT quantity, avg_entry_price FROM paper_portfolio WHERE symbol = $1",
                    symbol,
                )

                if existing and side == "BUY":
                    old_qty = float(existing["quantity"])
                    old_avg = float(existing["avg_entry_price"])
                    new_qty = old_qty + quantity
                    new_avg = (
                        (old_avg * old_qty + entry_price * quantity) / new_qty
                        if new_qty > 0
                        else 0
                    )
                    await conn.execute(
                        """
                        UPDATE paper_portfolio
                        SET quantity = $1, avg_entry_price = $2, updated_at = NOW()
                        WHERE symbol = $3
                        """,
                        Decimal(str(new_qty)),
                        Decimal(str(new_avg)),
                        symbol,
                    )
                elif existing and side == "SELL":
                    old_qty = float(existing["quantity"])
                    new_qty = old_qty - quantity
                    if new_qty <= 0:
                        await conn.execute(
                            "DELETE FROM paper_portfolio WHERE symbol = $1",
                            symbol,
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE paper_portfolio
                            SET quantity = $1, updated_at = NOW()
                            WHERE symbol = $2
                            """,
                            Decimal(str(new_qty)),
                            symbol,
                        )
                elif side == "BUY":
                    await conn.execute(
                        """
                        INSERT INTO paper_portfolio (symbol, quantity, avg_entry_price)
                        VALUES ($1, $2, $3)
                        """,
                        symbol,
                        Decimal(str(quantity)),
                        Decimal(str(entry_price)),
                    )

                return {
                    "trade_id": trade_id,
                    "session_id": session_id,
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "status": "OPEN",
                    "opened_at": row["opened_at"].isoformat(),
                }

    async def get_session_portfolio(
        self, session_id: str
    ) -> List[Dict[str, Any]]:
        """Get portfolio positions for trades in a specific session."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol,
                       SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS quantity,
                       AVG(CASE WHEN side = 'BUY' THEN entry_price END) AS avg_entry_price
                FROM paper_trades
                WHERE session_id = $1 AND status = 'OPEN'
                GROUP BY symbol
                HAVING SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) > 0
                """,
                session_id,
            )
            return [
                {
                    "symbol": row["symbol"],
                    "quantity": float(row["quantity"]),
                    "avg_entry_price": (
                        float(row["avg_entry_price"]) if row["avg_entry_price"] else 0.0
                    ),
                    "unrealized_pnl": 0.0,
                }
                for row in rows
            ]

    async def get_session_trades(
        self,
        session_id: str,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get trades for a specific session."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        conditions = ["session_id = $1"]
        params: list = [session_id]
        idx = 2

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT id, signal_id, symbol, side, entry_price, exit_price,
               quantity, pnl, opened_at, closed_at, status
        FROM paper_trades
        {where}
        ORDER BY opened_at DESC
        LIMIT ${idx}
        """
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                {
                    "trade_id": str(row["id"]),
                    "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "entry_price": float(row["entry_price"]),
                    "exit_price": (
                        float(row["exit_price"]) if row["exit_price"] else None
                    ),
                    "quantity": float(row["quantity"]),
                    "pnl": float(row["pnl"]) if row["pnl"] else None,
                    "opened_at": row["opened_at"].isoformat(),
                    "closed_at": (
                        row["closed_at"].isoformat() if row["closed_at"] else None
                    ),
                    "status": row["status"],
                }
                for row in rows
            ]

    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get performance stats for a paper trading session."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            session = await conn.fetchrow(
                """
                SELECT starting_balance, current_balance, total_realized_pnl, total_trades
                FROM paper_trading_sessions WHERE id = $1
                """,
                session_id,
            )
            if not session:
                return {}

            stats_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(pnl), 0) AS total_pnl,
                    COUNT(*) AS closed_trades,
                    COUNT(*) FILTER (WHERE pnl > 0) AS winning_trades,
                    COUNT(*) FILTER (WHERE pnl < 0) AS losing_trades,
                    COALESCE(AVG(pnl), 0) AS avg_pnl,
                    COALESCE(MAX(pnl), 0) AS best_trade,
                    COALESCE(MIN(pnl), 0) AS worst_trade
                FROM paper_trades
                WHERE session_id = $1 AND status = 'CLOSED'
                """,
                session_id,
            )

            starting = float(session["starting_balance"])
            current = float(session["current_balance"])
            total_pnl = float(stats_row["total_pnl"])
            closed = stats_row["closed_trades"] or 0
            wins = stats_row["winning_trades"] or 0
            win_rate = (wins / closed * 100) if closed > 0 else 0.0
            return_pct = (total_pnl / starting * 100) if starting > 0 else 0.0

            return {
                "starting_balance": starting,
                "current_balance": current,
                "total_pnl": total_pnl,
                "return_pct": round(return_pct, 4),
                "total_trades": session["total_trades"],
                "closed_trades": closed,
                "winning_trades": wins,
                "losing_trades": stats_row["losing_trades"] or 0,
                "win_rate": round(win_rate, 2),
                "avg_pnl": float(stats_row["avg_pnl"]),
                "best_trade": float(stats_row["best_trade"]),
                "worst_trade": float(stats_row["worst_trade"]),
            }

    async def get_live_trade_stats(self) -> Dict[str, Any]:
        """Get performance stats from live (non-session) trades for comparison."""
        if not self.pool:
            raise RuntimeError("PostgreSQL connection not established")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(pnl), 0) AS total_pnl,
                    COUNT(*) AS total_trades,
                    COUNT(*) FILTER (WHERE pnl > 0) AS winning_trades,
                    COUNT(*) FILTER (WHERE pnl < 0) AS losing_trades,
                    COALESCE(AVG(pnl), 0) AS avg_pnl,
                    COALESCE(MAX(pnl), 0) AS best_trade,
                    COALESCE(MIN(pnl), 0) AS worst_trade
                FROM paper_trades
                WHERE session_id IS NULL AND status = 'CLOSED'
                """
            )

            total = row["total_trades"] or 0
            wins = row["winning_trades"] or 0
            win_rate = (wins / total * 100) if total > 0 else 0.0

            return {
                "total_pnl": float(row["total_pnl"]),
                "return_pct": 0.0,
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": row["losing_trades"] or 0,
                "win_rate": round(win_rate, 2),
                "avg_pnl": float(row["avg_pnl"]),
                "best_trade": float(row["best_trade"]),
                "worst_trade": float(row["worst_trade"]),
            }

    @staticmethod
    def _session_row_to_dict(row) -> Dict[str, Any]:
        """Convert a session DB row to a dict."""
        result = {
            "session_id": str(row["id"]),
            "starting_balance": float(row["starting_balance"]),
            "current_balance": float(row["current_balance"]),
            "status": row["status"],
            "started_at": row["started_at"].isoformat(),
            "total_realized_pnl": float(row["total_realized_pnl"]),
            "total_trades": row["total_trades"],
        }
        if row.get("stopped_at"):
            result["stopped_at"] = row["stopped_at"].isoformat()
        return result
