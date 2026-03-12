"""
Learning Engine REST API — RMM Level 2.

Provides endpoints for decision tracking, pattern detection,
performance analytics, and similarity search.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class DecisionCreate(BaseModel):
    signal_id: str = Field(..., description="Associated signal UUID")
    agent_name: str = Field(..., description="Name of the deciding agent")
    decision_type: str = Field(..., description="Decision category")
    score: float = Field(..., description="Decision score (0-1)")
    tier: str = Field(..., description="Decision tier")
    reasoning: str = Field(..., description="Decision reasoning text")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None, description="Tool calls made"
    )
    model_used: Optional[str] = Field(None, description="LLM model used")
    latency_ms: Optional[int] = Field(None, description="Processing latency in ms")
    tokens_used: Optional[int] = Field(None, description="Token count")


class OutcomeUpdate(BaseModel):
    success: bool = Field(..., description="Whether the decision was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class MarketContext(BaseModel):
    instrument: str = Field(..., description="Trading instrument")
    price: float = Field(..., description="Current price")
    volatility: Optional[float] = Field(None, description="Current volatility")
    volume: Optional[float] = Field(None, description="Current volume")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Learning Engine API FastAPI application."""
    app = FastAPI(
        title="Learning Engine API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/learning",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("learning-api", check_deps))

    decisions_router = APIRouter(prefix="/decisions", tags=["Decisions"])

    # --- Decision endpoints ---

    @decisions_router.get("")
    async def list_decisions(
        pagination: PaginationParams = Depends(),
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
        from_date: Optional[str] = Query(
            None, alias="from", description="Start datetime (ISO 8601)"
        ),
    ):
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if from_date:
            idx += 1
            conditions.append(f"ad.created_at >= ${idx}::timestamptz")
            params.append(from_date)

        # Filter by instrument via joined signals table
        if instrument:
            idx += 1
            conditions.append(
                f"ad.signal_id IN (SELECT signal_id::text FROM signals WHERE symbol = ${idx})"
            )
            params.append(instrument)

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT ad.id, ad.signal_id, ad.agent_name, ad.decision_type,
                   ad.score, ad.tier, ad.reasoning, ad.tool_calls,
                   ad.model_used, ad.latency_ms, ad.tokens_used,
                   ad.success, ad.error_message, ad.created_at
            FROM agent_decisions ad
            WHERE {where}
            ORDER BY ad.created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM agent_decisions ad WHERE {where}"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "decision",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @decisions_router.post("", status_code=201)
    async def create_decision(body: DecisionCreate):
        query = """
            INSERT INTO agent_decisions
                (signal_id, agent_name, decision_type, score, tier,
                 reasoning, tool_calls, model_used, latency_ms, tokens_used)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.signal_id,
                    body.agent_name,
                    body.decision_type,
                    body.score,
                    body.tier,
                    body.reasoning,
                    json.dumps(body.tool_calls) if body.tool_calls else None,
                    body.model_used,
                    body.latency_ms,
                    body.tokens_used,
                )
        except Exception as e:
            logger.error("Failed to create decision: %s", e)
            return server_error(str(e))

        return success_response(
            data={
                "signal_id": body.signal_id,
                "agent_name": body.agent_name,
                "score": body.score,
                "tier": body.tier,
                "created_at": row["created_at"].isoformat(),
            },
            resource_type="decision",
            resource_id=str(row["id"]),
            status_code=201,
        )

    @decisions_router.get("/{decision_id}")
    async def get_decision(decision_id: str):
        query = """
            SELECT id, signal_id, agent_name, decision_type,
                   score, tier, reasoning, tool_calls,
                   model_used, latency_ms, tokens_used,
                   success, error_message, created_at
            FROM agent_decisions
            WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, decision_id)
        if not row:
            return not_found("Decision", decision_id)
        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "decision", resource_id=item["id"])

    @decisions_router.put("/{decision_id}/outcome")
    async def record_outcome(decision_id: str, body: OutcomeUpdate):
        query = """
            UPDATE agent_decisions
            SET success = $2, error_message = $3
            WHERE id = $1::uuid
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                query, decision_id, body.success, body.error_message
            )
        if not row:
            return not_found("Decision", decision_id)
        return success_response(
            {"success": body.success, "error_message": body.error_message},
            "outcome",
            resource_id=decision_id,
        )

    # --- Analytics endpoints ---

    @app.get("/patterns", tags=["Analytics"])
    async def get_patterns():
        """Detect performance patterns from recent decisions."""
        query = """
            SELECT agent_name,
                   tier,
                   COUNT(*) as count,
                   AVG(score) as avg_score,
                   SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successes,
                   SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failures
            FROM agent_decisions
            WHERE created_at > NOW() - INTERVAL '30 days'
              AND agent_name IS NOT NULL
            GROUP BY agent_name, tier
            ORDER BY count DESC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        items = [dict(row) for row in rows]
        for item in items:
            if item.get("avg_score") is not None:
                item["avg_score"] = float(item["avg_score"])
        return collection_response(items, "pattern")

    @app.get("/performance", tags=["Analytics"])
    async def get_performance(
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
        period: str = Query(
            "30d", description="Time period", regex="^(7d|30d|90d|all)$"
        ),
    ):
        """Get aggregate performance metrics."""
        interval_map = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}
        interval = interval_map.get(period)

        conditions = ["1=1"]
        params: list = []
        idx = 0

        if interval:
            idx += 1
            conditions.append(f"ad.created_at > NOW() - INTERVAL '{interval}'")

        if instrument:
            idx += 1
            conditions.append(
                f"ad.signal_id IN (SELECT signal_id::text FROM signals WHERE symbol = ${idx})"
            )
            params.append(instrument)

        where = " AND ".join(conditions)
        query = f"""
            SELECT COUNT(*) as total_decisions,
                   AVG(ad.score) as avg_score,
                   AVG(ad.latency_ms) as avg_latency_ms,
                   SUM(CASE WHEN ad.success = true THEN 1 ELSE 0 END) as successes,
                   SUM(CASE WHEN ad.success = false THEN 1 ELSE 0 END) as failures,
                   COUNT(DISTINCT ad.agent_name) as unique_agents
            FROM agent_decisions ad
            WHERE {where}
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        metrics = dict(row)
        if metrics.get("avg_score") is not None:
            metrics["avg_score"] = float(metrics["avg_score"])
        if metrics.get("avg_latency_ms") is not None:
            metrics["avg_latency_ms"] = float(metrics["avg_latency_ms"])
        metrics["period"] = period
        return success_response(metrics, "performance_metrics")

    @app.post("/similar", tags=["Analytics"])
    async def find_similar(body: MarketContext):
        """Find similar historical situations based on market context."""
        # Look for signals in the same instrument near the same price level
        query = """
            SELECT s.signal_id, s.symbol, s.action, s.confidence,
                   s.price, s.created_at,
                   ad.score, ad.tier, ad.success
            FROM signals s
            LEFT JOIN agent_decisions ad ON ad.signal_id = s.signal_id::text
            WHERE s.symbol = $1
            ORDER BY ABS(s.price - $2) ASC
            LIMIT 10
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, body.instrument, body.price)

        items = []
        for row in rows:
            item = dict(row)
            item["signal_id"] = str(item["signal_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("price") is not None:
                item["price"] = float(item["price"])
            items.append(item)
        return collection_response(items, "similar_situation")

    app.include_router(decisions_router)
    return app
