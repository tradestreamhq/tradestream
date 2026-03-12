"""
Liquidity Scoring REST API — RMM Level 2.

Provides endpoints for querying and computing asset liquidity scores.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

from services.liquidity_scoring.models import LiquidityCategory, LiquidityMetrics, LiquidityScore
from services.liquidity_scoring.scorer import compute_score
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


class LiquidityMetricsInput(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol, e.g. BTC/USD")
    avg_daily_volume_30d: float = Field(..., ge=0, description="30-day average daily volume in USD")
    avg_spread_pct: float = Field(..., ge=0, description="Average bid-ask spread as a percentage")
    order_book_depth_usd: float = Field(..., ge=0, description="Order book depth in USD")
    trade_frequency_per_hour: float = Field(..., ge=0, description="Average trades per hour")


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Liquidity Scoring API FastAPI application."""
    app = FastAPI(
        title="Liquidity Scoring API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/liquidity",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("liquidity-scoring", check_deps))

    @app.get("/{symbol}", tags=["Liquidity"])
    async def get_liquidity_score(symbol: str):
        """Get the most recent liquidity score for a symbol."""
        query = """
            SELECT symbol, score, category,
                   volume_component, spread_component,
                   depth_component, frequency_component,
                   scored_at
            FROM liquidity_scores
            WHERE symbol = $1
            ORDER BY scored_at DESC
            LIMIT 1
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, symbol)
        if not row:
            return not_found("Liquidity score", symbol)
        item = dict(row)
        item["score"] = float(item["score"])
        item["volume_component"] = float(item["volume_component"])
        item["spread_component"] = float(item["spread_component"])
        item["depth_component"] = float(item["depth_component"])
        item["frequency_component"] = float(item["frequency_component"])
        if item.get("scored_at"):
            item["scored_at"] = item["scored_at"].isoformat()
        return success_response(item, "liquidity_score", resource_id=symbol)

    @app.get("/{symbol}/history", tags=["Liquidity"])
    async def get_liquidity_history(
        symbol: str,
        limit: int = Query(default=30, ge=1, le=365),
        offset: int = Query(default=0, ge=0),
    ):
        """Get historical liquidity scores for a symbol."""
        query = """
            SELECT symbol, score, category, scored_at
            FROM liquidity_scores
            WHERE symbol = $1
            ORDER BY scored_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM liquidity_scores WHERE symbol = $1
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, limit, offset)
            total = await conn.fetchval(count_query, symbol)

        items = []
        for row in rows:
            item = dict(row)
            item["score"] = float(item["score"])
            if item.get("scored_at"):
                item["scored_at"] = item["scored_at"].isoformat()
            items.append(item)
        return collection_response(items, "liquidity_score", total=total, limit=limit, offset=offset)

    @app.get("/", tags=["Liquidity"])
    async def list_liquidity_scores(
        category: Optional[str] = Query(default=None, description="Filter by category: high, medium, low"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ):
        """List latest liquidity scores for all tracked symbols."""
        base_query = """
            SELECT DISTINCT ON (symbol)
                   symbol, score, category,
                   volume_component, spread_component,
                   depth_component, frequency_component,
                   scored_at
            FROM liquidity_scores
            {where}
            ORDER BY symbol, scored_at DESC
        """
        where = ""
        params: list = []
        if category:
            if category not in ("high", "medium", "low"):
                return validation_error(f"Invalid category '{category}'. Must be high, medium, or low.")
            where = "WHERE category = $1"
            params.append(category)

        # Wrap in subquery for pagination
        query = f"""
            SELECT * FROM ({base_query.format(where=where)}) sub
            ORDER BY score DESC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """
        params.extend([limit, offset])

        count_query = f"""
            SELECT COUNT(*) FROM ({base_query.format(where=where)}) sub
        """
        count_params = [category] if category else []

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *count_params) if count_params else await conn.fetchval(count_query)

        items = []
        for row in rows:
            item = dict(row)
            item["score"] = float(item["score"])
            item["volume_component"] = float(item["volume_component"])
            item["spread_component"] = float(item["spread_component"])
            item["depth_component"] = float(item["depth_component"])
            item["frequency_component"] = float(item["frequency_component"])
            if item.get("scored_at"):
                item["scored_at"] = item["scored_at"].isoformat()
            items.append(item)
        return collection_response(items, "liquidity_score", total=total, limit=limit, offset=offset)

    @app.post("/score", tags=["Liquidity"])
    async def score_asset(body: LiquidityMetricsInput):
        """Compute and store a liquidity score for an asset."""
        metrics = LiquidityMetrics(
            symbol=body.symbol,
            avg_daily_volume_30d=body.avg_daily_volume_30d,
            avg_spread_pct=body.avg_spread_pct,
            order_book_depth_usd=body.order_book_depth_usd,
            trade_frequency_per_hour=body.trade_frequency_per_hour,
        )
        total, vol, spread, depth, freq = compute_score(metrics)
        category = LiquidityScore.categorize(total)
        scored_at = datetime.now(timezone.utc)

        insert_query = """
            INSERT INTO liquidity_scores
                (symbol, score, category, volume_component, spread_component,
                 depth_component, frequency_component, scored_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row_id = await conn.fetchval(
                insert_query,
                body.symbol,
                total,
                category.value,
                vol,
                spread,
                depth,
                freq,
                scored_at,
            )

        result = {
            "symbol": body.symbol,
            "score": total,
            "category": category.value,
            "volume_component": vol,
            "spread_component": spread,
            "depth_component": depth,
            "frequency_component": freq,
            "scored_at": scored_at.isoformat(),
        }
        return success_response(result, "liquidity_score", resource_id=str(row_id))

    return app
