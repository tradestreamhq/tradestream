"""Strategy Scheduler REST API.

Provides GET/PUT endpoints for strategy schedule management
and a status endpoint for evaluating current schedule state.
"""

import json
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, FastAPI

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.strategy_scheduler.models import (
    MarketPhase,
    ScheduleCreate,
    ScheduleStatus,
)
from services.strategy_scheduler.scheduler import (
    should_strategy_run,
    validate_cron,
)

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Scheduler FastAPI application."""
    app = FastAPI(
        title="Strategy Scheduler API",
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

    app.include_router(create_health_router("strategy-scheduler", check_deps))

    router = APIRouter(tags=["Schedule"])

    @router.get("/{strategy_id}/schedule")
    async def get_schedule(strategy_id: str):
        """Get the schedule for a strategy."""
        query = """
            SELECT strategy_id, active_hours_start, active_hours_end,
                   market_phases, cron_expression, timezone, enabled,
                   created_at, updated_at
            FROM strategy_schedules
            WHERE strategy_id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, strategy_id)
        if not row:
            return not_found("Schedule", strategy_id)
        item = dict(row)
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "strategy_schedule", resource_id=item["strategy_id"])

    @router.put("/{strategy_id}/schedule")
    async def put_schedule(strategy_id: str, body: ScheduleCreate):
        """Create or update the schedule for a strategy."""
        # Validate cron expression if provided
        if body.cron_expression and not validate_cron(body.cron_expression):
            return validation_error(
                "Invalid cron expression. Expected 5 fields: minute hour day month weekday"
            )

        phases_json = json.dumps([p.value for p in body.market_phases])

        upsert = """
            INSERT INTO strategy_schedules
                (strategy_id, active_hours_start, active_hours_end,
                 market_phases, cron_expression, timezone, enabled)
            VALUES ($1::uuid, $2, $3, $4::jsonb, $5, $6, $7)
            ON CONFLICT (strategy_id) DO UPDATE SET
                active_hours_start = EXCLUDED.active_hours_start,
                active_hours_end = EXCLUDED.active_hours_end,
                market_phases = EXCLUDED.market_phases,
                cron_expression = EXCLUDED.cron_expression,
                timezone = EXCLUDED.timezone,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING strategy_id, active_hours_start, active_hours_end,
                      market_phases, cron_expression, timezone, enabled,
                      created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    upsert,
                    strategy_id,
                    body.active_hours_start,
                    body.active_hours_end,
                    phases_json,
                    body.cron_expression,
                    body.timezone,
                    body.enabled,
                )
        except asyncpg.ForeignKeyViolationError:
            return not_found("Strategy", strategy_id)
        except Exception as e:
            logger.error("Failed to upsert schedule: %s", e)
            return validation_error(str(e))

        item = dict(row)
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "strategy_schedule", resource_id=item["strategy_id"])

    @router.get("/{strategy_id}/schedule/status")
    async def get_schedule_status(strategy_id: str):
        """Evaluate the current schedule status for a strategy."""
        query = """
            SELECT strategy_id, active_hours_start, active_hours_end,
                   market_phases, cron_expression, timezone, enabled
            FROM strategy_schedules
            WHERE strategy_id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, strategy_id)
        if not row:
            return not_found("Schedule", strategy_id)

        phases = [MarketPhase(p) for p in row["market_phases"]]
        run, phase, in_hours, cron_ok = should_strategy_run(
            enabled=row["enabled"],
            market_phases=phases,
            active_hours_start=row["active_hours_start"],
            active_hours_end=row["active_hours_end"],
            cron_expression=row["cron_expression"],
        )

        status = ScheduleStatus(
            strategy_id=str(row["strategy_id"]),
            should_run=run,
            current_market_phase=phase,
            in_active_hours=in_hours,
            cron_match=cron_ok,
            enabled=row["enabled"],
        )
        return success_response(
            status.model_dump(), "schedule_status", resource_id=status.strategy_id
        )

    app.include_router(router)
    return app
