"""
Signal REST API — Phase 3 Signal MVP.

Provides endpoints for signal subscription, retrieval, history,
and per-strategy performance tracking.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class SubscribeRequest(BaseModel):
    channel: str = Field(
        ...,
        description="Delivery channel: 'telegram' or 'webhook'",
        pattern="^(telegram|webhook)$",
    )
    endpoint: str = Field(
        ...,
        description="Telegram chat_id or webhook URL",
    )
    strategies: Optional[List[str]] = Field(
        None,
        description="Filter to specific strategy names; null = all",
    )
    pairs: Optional[List[str]] = Field(
        None,
        description="Filter to specific trading pairs; null = all",
    )


class UnsubscribeRequest(BaseModel):
    subscription_id: str = Field(..., description="Subscription UUID to remove")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Signal API FastAPI application."""
    app = FastAPI(
        title="Signal API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/signals",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("signal-api", check_deps))

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    @app.post("/subscribe", tags=["Subscriptions"])
    async def subscribe(body: SubscribeRequest):
        """Subscribe to trading signals via Telegram or webhook."""
        sub_id = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM signal_subscriptions "
                "WHERE channel = $1 AND endpoint = $2 AND active = true",
                body.channel,
                body.endpoint,
            )
            if existing:
                return conflict(
                    f"Active subscription already exists for {body.channel}:{body.endpoint}"
                )

            await conn.execute(
                """INSERT INTO signal_subscriptions
                   (id, channel, endpoint, strategies, pairs, active, created_at)
                   VALUES ($1, $2, $3, $4, $5, true, NOW())""",
                sub_id,
                body.channel,
                body.endpoint,
                body.strategies,
                body.pairs,
            )

        return success_response(
            {"subscription_id": sub_id, "channel": body.channel, "endpoint": body.endpoint},
            "subscription",
            resource_id=sub_id,
            status_code=201,
        )

    @app.delete("/subscribe/{subscription_id}", tags=["Subscriptions"])
    async def unsubscribe(subscription_id: str):
        """Deactivate a signal subscription."""
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE signal_subscriptions SET active = false WHERE id = $1 AND active = true",
                subscription_id,
            )
        if result == "UPDATE 0":
            return not_found("Subscription", subscription_id)
        return success_response(
            {"subscription_id": subscription_id, "status": "unsubscribed"},
            "subscription",
            resource_id=subscription_id,
        )

    @app.get("/subscribe", tags=["Subscriptions"])
    async def list_subscriptions():
        """List all active subscriptions."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, channel, endpoint, strategies, pairs, created_at "
                "FROM signal_subscriptions WHERE active = true ORDER BY created_at DESC"
            )
        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(items, "subscription")

    # ------------------------------------------------------------------
    # Latest signals
    # ------------------------------------------------------------------

    @app.get("/", tags=["Signals"])
    async def get_latest_signals(
        limit: int = Query(20, ge=1, le=100),
        strategy: Optional[str] = Query(None),
        pair: Optional[str] = Query(None),
    ):
        """Get the most recent trading signals."""
        conditions = []
        params: list = []
        idx = 1

        if strategy:
            conditions.append(f"s.strategy_name = ${idx}")
            params.append(strategy)
            idx += 1
        if pair:
            conditions.append(f"s.instrument = ${idx}")
            params.append(pair)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        query = f"""
            SELECT s.id, s.strategy_name, s.instrument, s.signal_type AS direction,
                   s.price AS entry_price, s.stop_loss, s.take_profit,
                   s.strength AS confidence, s.created_at AS timestamp
            FROM signals s
            {where}
            ORDER BY s.created_at DESC
            LIMIT ${idx}
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = [_format_signal(row) for row in rows]
        return collection_response(items, "signal")

    # ------------------------------------------------------------------
    # Signal history
    # ------------------------------------------------------------------

    @app.get("/history", tags=["Signals"])
    async def get_signal_history(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        strategy: Optional[str] = Query(None),
        pair: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None, description="ISO date yyyy-mm-dd"),
        end_date: Optional[str] = Query(None, description="ISO date yyyy-mm-dd"),
    ):
        """Query signal history with filtering by strategy, pair, and date range."""
        conditions = []
        params: list = []
        idx = 1

        if strategy:
            conditions.append(f"s.strategy_name = ${idx}")
            params.append(strategy)
            idx += 1
        if pair:
            conditions.append(f"s.instrument = ${idx}")
            params.append(pair)
            idx += 1
        if start_date:
            conditions.append(f"s.created_at >= ${idx}::timestamptz")
            params.append(start_date)
            idx += 1
        if end_date:
            conditions.append(f"s.created_at < (${idx}::date + interval '1 day')")
            params.append(end_date)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_query = f"SELECT COUNT(*) FROM signals s {where}"
        data_query = f"""
            SELECT s.id, s.strategy_name, s.instrument, s.signal_type AS direction,
                   s.price AS entry_price, s.stop_loss, s.take_profit,
                   s.strength AS confidence, s.outcome, s.exit_price,
                   s.pnl, s.pnl_percent, s.created_at AS timestamp
            FROM signals s
            {where}
            ORDER BY s.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params_with_paging = params + [limit, offset]

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(data_query, *params_with_paging)

        items = [_format_signal(row) for row in rows]
        return collection_response(items, "signal", total=total, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Performance tracking
    # ------------------------------------------------------------------

    @app.get("/performance", tags=["Performance"])
    async def get_performance(
        strategy: Optional[str] = Query(None),
    ):
        """Get signal performance metrics per strategy."""
        condition = ""
        params: list = []
        if strategy:
            condition = "WHERE strategy_name = $1"
            params = [strategy]

        query = f"""
            SELECT
                strategy_name,
                COUNT(*) AS total_signals,
                COUNT(*) FILTER (WHERE outcome = 'PROFIT') AS wins,
                COUNT(*) FILTER (WHERE outcome = 'LOSS') AS losses,
                COUNT(*) FILTER (WHERE outcome = 'PENDING') AS pending,
                ROUND(
                    COUNT(*) FILTER (WHERE outcome = 'PROFIT')::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE outcome IN ('PROFIT', 'LOSS')), 0)
                    * 100, 2
                ) AS win_rate_pct,
                ROUND(COALESCE(AVG(pnl_percent) FILTER (WHERE outcome IN ('PROFIT', 'LOSS')), 0), 4) AS avg_return_pct,
                ROUND(COALESCE(MIN(pnl_percent) FILTER (WHERE outcome = 'LOSS'), 0), 4) AS max_drawdown_pct,
                ROUND(COALESCE(SUM(pnl), 0), 2) AS total_pnl
            FROM signals
            {condition}
            GROUP BY strategy_name
            ORDER BY win_rate_pct DESC NULLS LAST
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            for key in ("win_rate_pct", "avg_return_pct", "max_drawdown_pct", "total_pnl"):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            items.append(item)

        return collection_response(items, "strategy_performance")

    return app


def _format_signal(row) -> Dict[str, Any]:
    """Convert a database row to a signal dict."""
    item = dict(row)
    item["id"] = str(item["id"])
    if item.get("entry_price") is not None:
        item["entry_price"] = float(item["entry_price"])
    if item.get("stop_loss") is not None:
        item["stop_loss"] = float(item["stop_loss"])
    if item.get("take_profit") is not None:
        item["take_profit"] = float(item["take_profit"])
    if item.get("confidence") is not None:
        item["confidence"] = float(item["confidence"])
    if item.get("pnl") is not None:
        item["pnl"] = float(item["pnl"])
    if item.get("pnl_percent") is not None:
        item["pnl_percent"] = float(item["pnl_percent"])
    if item.get("exit_price") is not None:
        item["exit_price"] = float(item["exit_price"])
    if item.get("timestamp"):
        item["timestamp"] = item["timestamp"].isoformat()
    return item
