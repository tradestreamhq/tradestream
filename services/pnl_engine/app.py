"""
PnL Engine REST API — RMM Level 2.

Provides endpoints for realized P&L, unrealized P&L, and combined summaries
with support for FIFO, LIFO, and average cost basis methods.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query

from services.pnl_engine.pnl_engine import (
    CostBasisMethod,
    Lot,
    PnLEngine,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def _build_engine(
    trades: List[Dict[str, Any]],
    method: CostBasisMethod,
) -> PnLEngine:
    """Build a PnLEngine from trade records, replaying buys and sells."""
    engine = PnLEngine(method=method)
    for t in trades:
        symbol = t["symbol"]
        price = Decimal(str(t["price"]))
        size = Decimal(str(t["size"]))
        ts = t["executed_at"]
        side = t["side"].upper()

        if side == "BUY":
            engine.add_buy(symbol, price, size, ts, lot_id=str(t.get("id", "")))
        elif side == "SELL":
            try:
                engine.add_sell(symbol, price, size, ts)
            except ValueError:
                logger.warning("Sell exceeds position for %s, skipping", symbol)
    return engine


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the PnL Engine FastAPI application."""
    app = FastAPI(
        title="PnL Engine API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/pnl",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("pnl-engine", check_deps))

    @app.get("/{strategy_id}/realized", tags=["PnL"])
    async def get_realized_pnl(
        strategy_id: str,
        method: str = Query("fifo", pattern="^(fifo|lifo|average)$"),
        start: Optional[str] = Query(None),
        end: Optional[str] = Query(None),
    ):
        """Get realized P&L breakdown by cost basis method."""
        try:
            cost_method = CostBasisMethod(method)
        except ValueError:
            return validation_error(f"Invalid method: {method}")

        query = """
            SELECT id, symbol, side, price, quantity as size, executed_at
            FROM paper_trades
            WHERE strategy_id = $1
              AND status = 'CLOSED'
            ORDER BY executed_at ASC
        """
        params: list = [strategy_id]

        time_filter = ""
        param_idx = 2
        if start:
            time_filter += f" AND executed_at >= ${param_idx}::timestamptz"
            params.append(start)
            param_idx += 1
        if end:
            time_filter += f" AND executed_at <= ${param_idx}::timestamptz"
            params.append(end)

        # Fetch all trades for the strategy to replay position
        all_trades_query = """
            SELECT id, symbol, side, price, quantity as size, executed_at
            FROM paper_trades
            WHERE strategy_id = $1
            ORDER BY executed_at ASC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(all_trades_query, strategy_id)

        if not rows:
            return collection_response([], "realized_pnl")

        trades = [dict(r) for r in rows]
        engine = _build_engine(trades, cost_method)

        # Collect realized PnL
        realized_items = []
        for symbol, pos in engine.positions.items():
            for r in pos.realized:
                item = {
                    "symbol": symbol,
                    "entry_price": float(r.lot_entry_price),
                    "exit_price": float(r.exit_price),
                    "size": float(r.size),
                    "pnl": float(r.pnl),
                    "pnl_pct": float(r.pnl_pct),
                    "lot_timestamp": r.lot_timestamp.isoformat()
                    if r.lot_timestamp
                    else None,
                    "exit_timestamp": r.exit_timestamp.isoformat()
                    if r.exit_timestamp
                    else None,
                }
                # Apply time filters on the realized events
                if start and r.exit_timestamp:
                    start_dt = datetime.fromisoformat(start)
                    if r.exit_timestamp.replace(tzinfo=None) < start_dt.replace(
                        tzinfo=None
                    ):
                        continue
                if end and r.exit_timestamp:
                    end_dt = datetime.fromisoformat(end)
                    if r.exit_timestamp.replace(tzinfo=None) > end_dt.replace(
                        tzinfo=None
                    ):
                        continue
                realized_items.append(item)

        return collection_response(realized_items, "realized_pnl")

    @app.get("/{strategy_id}/unrealized", tags=["PnL"])
    async def get_unrealized_pnl(strategy_id: str):
        """Get current unrealized P&L by position."""
        trades_query = """
            SELECT id, symbol, side, price, quantity as size, executed_at
            FROM paper_trades
            WHERE strategy_id = $1
            ORDER BY executed_at ASC
        """
        prices_query = """
            SELECT symbol, price as current_price
            FROM latest_prices
            WHERE symbol IN (
                SELECT DISTINCT symbol FROM paper_trades WHERE strategy_id = $1
            )
        """
        async with db_pool.acquire() as conn:
            trade_rows = await conn.fetch(trades_query, strategy_id)
            price_rows = await conn.fetch(prices_query, strategy_id)

        if not trade_rows:
            return collection_response([], "unrealized_pnl")

        trades = [dict(r) for r in trade_rows]
        current_prices = {r["symbol"]: Decimal(str(r["current_price"])) for r in price_rows}

        engine = _build_engine(trades, CostBasisMethod.FIFO)

        unrealized_items = []
        for symbol, pos in engine.positions.items():
            if pos.total_size <= 0:
                continue
            mark_price = current_prices.get(symbol, pos.avg_entry_price)
            total_unrealized = pos.total_unrealized_pnl(mark_price)
            unrealized_items.append(
                {
                    "symbol": symbol,
                    "size": float(pos.total_size),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "current_price": float(mark_price),
                    "unrealized_pnl": float(total_unrealized),
                    "lot_count": len(pos.lots),
                    "lots": [
                        {
                            "entry_price": float(lot.entry_price),
                            "size": float(lot.size),
                            "timestamp": lot.timestamp.isoformat(),
                            "unrealized_pnl": float(
                                (mark_price - lot.entry_price) * lot.size
                            ),
                        }
                        for lot in pos.lots
                    ],
                }
            )

        return collection_response(unrealized_items, "unrealized_pnl")

    @app.get("/{strategy_id}/summary", tags=["PnL"])
    async def get_pnl_summary(
        strategy_id: str,
        method: str = Query("fifo", pattern="^(fifo|lifo|average)$"),
    ):
        """Get combined realized + unrealized P&L summary."""
        try:
            cost_method = CostBasisMethod(method)
        except ValueError:
            return validation_error(f"Invalid method: {method}")

        trades_query = """
            SELECT id, symbol, side, price, quantity as size, executed_at
            FROM paper_trades
            WHERE strategy_id = $1
            ORDER BY executed_at ASC
        """
        prices_query = """
            SELECT symbol, price as current_price
            FROM latest_prices
            WHERE symbol IN (
                SELECT DISTINCT symbol FROM paper_trades WHERE strategy_id = $1
            )
        """
        async with db_pool.acquire() as conn:
            trade_rows = await conn.fetch(trades_query, strategy_id)
            price_rows = await conn.fetch(prices_query, strategy_id)

        if not trade_rows:
            return success_response(
                {
                    "strategy_id": strategy_id,
                    "method": method,
                    "total_realized_pnl": 0.0,
                    "total_unrealized_pnl": 0.0,
                    "total_pnl": 0.0,
                    "open_positions": 0,
                    "closed_trades": 0,
                },
                "pnl_summary",
                resource_id=strategy_id,
            )

        trades = [dict(r) for r in trade_rows]
        current_prices = {r["symbol"]: Decimal(str(r["current_price"])) for r in price_rows}

        engine = _build_engine(trades, cost_method)

        total_realized = Decimal(0)
        total_unrealized = Decimal(0)
        closed_count = 0
        open_count = 0

        for symbol, pos in engine.positions.items():
            total_realized += pos.total_realized_pnl
            closed_count += len(pos.realized)
            if pos.total_size > 0:
                open_count += 1
                mark = current_prices.get(symbol, pos.avg_entry_price)
                total_unrealized += pos.total_unrealized_pnl(mark)

        return success_response(
            {
                "strategy_id": strategy_id,
                "method": method,
                "total_realized_pnl": float(total_realized),
                "total_unrealized_pnl": float(total_unrealized),
                "total_pnl": float(total_realized + total_unrealized),
                "open_positions": open_count,
                "closed_trades": closed_count,
            },
            "pnl_summary",
            resource_id=strategy_id,
        )

    return app
