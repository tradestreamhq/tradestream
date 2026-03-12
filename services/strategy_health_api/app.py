"""
Strategy Health Monitoring REST API.

Tracks strategy uptime, heartbeats, error rates, and operational metrics.
Health status levels: healthy, degraded, unhealthy, offline.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

# Default timeout: mark offline if no heartbeat for this many seconds.
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes

# Thresholds for health status derivation.
ERROR_RATE_DEGRADED = 5  # errors >= 5 → degraded
ERROR_RATE_UNHEALTHY = 20  # errors >= 20 → unhealthy


class HeartbeatRequest(BaseModel):
    error_count: Optional[int] = Field(0, description="Errors since last heartbeat")
    warning_count: Optional[int] = Field(0, description="Warnings since last heartbeat")
    error_message: Optional[str] = Field(None, description="Latest error message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extra operational data")


def compute_health_status(
    last_heartbeat: Optional[datetime],
    error_count: int,
    now: Optional[datetime] = None,
    timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
) -> str:
    """Derive health status from heartbeat age and error count."""
    if now is None:
        now = datetime.now(timezone.utc)

    if last_heartbeat is None:
        return "offline"

    age = (now - last_heartbeat).total_seconds()
    if age > timeout_seconds:
        return "offline"

    if error_count >= ERROR_RATE_UNHEALTHY:
        return "unhealthy"
    if error_count >= ERROR_RATE_DEGRADED:
        return "degraded"

    return "healthy"


def create_app(
    db_pool: asyncpg.Pool,
    heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
) -> FastAPI:
    """Create the Strategy Health API FastAPI application."""
    app = FastAPI(
        title="Strategy Health Monitoring API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategies",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-health-api", check_deps))

    router = APIRouter(tags=["Strategy Health"])

    # --- POST /strategies/{strategy_id}/heartbeat ---

    @router.post("/strategies/{strategy_id}/heartbeat")
    async def post_heartbeat(strategy_id: str, body: HeartbeatRequest):
        now = datetime.now(timezone.utc)
        new_errors = body.error_count or 0
        new_warnings = body.warning_count or 0
        meta = json.dumps(body.metadata) if body.metadata else "{}"

        upsert = """
            INSERT INTO strategy_health_checks
                (strategy_id, status, last_heartbeat, error_count, warning_count,
                 last_error_msg, metadata, uptime_pct)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, 100.00)
            ON CONFLICT (strategy_id) DO UPDATE SET
                last_heartbeat = EXCLUDED.last_heartbeat,
                error_count    = strategy_health_checks.error_count + EXCLUDED.error_count,
                warning_count  = strategy_health_checks.warning_count + EXCLUDED.warning_count,
                last_error_msg = COALESCE(EXCLUDED.last_error_msg, strategy_health_checks.last_error_msg),
                metadata       = EXCLUDED.metadata,
                status         = $2
            RETURNING id, strategy_id, status, last_heartbeat, uptime_pct,
                      error_count, warning_count, last_error_msg, metadata
        """
        try:
            async with db_pool.acquire() as conn:
                # Fetch current error_count to compute new status
                existing = await conn.fetchrow(
                    "SELECT error_count FROM strategy_health_checks WHERE strategy_id = $1::uuid",
                    strategy_id,
                )
                total_errors = (existing["error_count"] if existing else 0) + new_errors
                status = compute_health_status(now, total_errors, now, heartbeat_timeout)

                row = await conn.fetchrow(
                    upsert,
                    strategy_id,
                    status,
                    now,
                    new_errors,
                    new_warnings,
                    body.error_message,
                    meta,
                )

                # Record history entry
                await conn.execute(
                    """
                    INSERT INTO strategy_health_history
                        (strategy_id, status, error_count, warning_count, last_error_msg)
                    VALUES ($1::uuid, $2, $3, $4, $5)
                    """,
                    strategy_id,
                    status,
                    row["error_count"],
                    row["warning_count"],
                    row["last_error_msg"],
                )
        except asyncpg.ForeignKeyViolationError:
            return not_found("Strategy", strategy_id)
        except Exception as e:
            logger.error("Heartbeat failed for %s: %s", strategy_id, e)
            return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("last_heartbeat"):
            item["last_heartbeat"] = item["last_heartbeat"].isoformat()
        item["uptime_pct"] = float(item["uptime_pct"])
        return success_response(item, "strategy_health", resource_id=item["id"])

    # --- GET /strategies/health ---

    @router.get("/strategies/health")
    async def get_all_health(pagination: PaginationParams = Depends()):
        now = datetime.now(timezone.utc)
        query = """
            SELECT id, strategy_id, status, last_heartbeat, uptime_pct,
                   error_count, warning_count, last_error_msg, metadata
            FROM strategy_health_checks
            ORDER BY last_heartbeat DESC NULLS LAST
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM strategy_health_checks"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, pagination.limit, pagination.offset)
            total = await conn.fetchval(count_query)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            # Recompute status to catch offline transitions
            item["status"] = compute_health_status(
                item["last_heartbeat"],
                item["error_count"],
                now,
                heartbeat_timeout,
            )
            if item.get("last_heartbeat"):
                item["last_heartbeat"] = item["last_heartbeat"].isoformat()
            item["uptime_pct"] = float(item["uptime_pct"])
            items.append(item)

        return collection_response(
            items,
            "strategy_health",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- GET /strategies/{strategy_id}/health/history ---

    @router.get("/strategies/{strategy_id}/health/history")
    async def get_health_history(
        strategy_id: str,
        pagination: PaginationParams = Depends(),
    ):
        query = """
            SELECT id, strategy_id, status, error_count, warning_count,
                   last_error_msg, recorded_at
            FROM strategy_health_history
            WHERE strategy_id = $1::uuid
            ORDER BY recorded_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM strategy_health_history
            WHERE strategy_id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, strategy_id, pagination.limit, pagination.offset)
            total = await conn.fetchval(count_query, strategy_id)

        if not rows and total == 0:
            # Check strategy exists at all
            async with db_pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM strategy_implementations WHERE id = $1::uuid",
                    strategy_id,
                )
            if not exists:
                return not_found("Strategy", strategy_id)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            if item.get("recorded_at"):
                item["recorded_at"] = item["recorded_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "strategy_health_history",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(router)
    return app
