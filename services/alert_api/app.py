"""Alert & Notification REST API — RMM Level 2.

Provides CRUD endpoints for alert rules and alert history retrieval.
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

VALID_CONDITION_TYPES = {
    "drawdown_exceeded",
    "pnl_target",
    "signal_generated",
    "consecutive_losses",
}


# --- Request / Response DTOs ---


class AlertRuleCreate(BaseModel):
    name: str = Field(..., description="Human-readable rule name")
    condition_type: str = Field(
        ...,
        description="One of: drawdown_exceeded, pnl_target, signal_generated, consecutive_losses",
    )
    threshold: Optional[float] = Field(
        None, description="Numeric threshold for the condition"
    )
    strategy_id: Optional[str] = Field(
        None, description="Optional strategy spec ID to scope the rule"
    )
    implementation_id: Optional[str] = Field(
        None, description="Optional implementation ID to scope the rule"
    )
    notification_channels: List[str] = Field(
        default_factory=list,
        description="Notification channels: in_app, email, webhook, etc.",
    )


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition_type: Optional[str] = None
    threshold: Optional[float] = None
    strategy_id: Optional[str] = None
    implementation_id: Optional[str] = None
    notification_channels: Optional[List[str]] = None
    is_active: Optional[bool] = None


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Alert API FastAPI application."""
    app = FastAPI(
        title="Alert & Notification API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/alerts",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("alert-api", check_deps))

    alerts_router = APIRouter(prefix="/alerts", tags=["Alerts"])

    # --- CRUD endpoints ---

    @alerts_router.post("", status_code=201)
    async def create_alert_rule(body: AlertRuleCreate):
        if body.condition_type not in VALID_CONDITION_TYPES:
            return validation_error(
                f"Invalid condition_type '{body.condition_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_CONDITION_TYPES))}"
            )

        query = """
            INSERT INTO alert_rules
                (name, condition_type, threshold, strategy_id, implementation_id,
                 notification_channels)
            VALUES ($1, $2, $3, $4::uuid, $5::uuid, $6)
            RETURNING id, name, condition_type, threshold, strategy_id,
                      implementation_id, notification_channels, is_active, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.name,
                    body.condition_type,
                    body.threshold,
                    body.strategy_id,
                    body.implementation_id,
                    body.notification_channels,
                )
        except Exception as e:
            logger.error("Failed to create alert rule: %s", e)
            return server_error(str(e))

        item = _row_to_dict(row)
        return success_response(
            data=item,
            resource_type="alert_rule",
            resource_id=item["id"],
            status_code=201,
        )

    @alerts_router.get("")
    async def list_alert_rules(
        pagination: PaginationParams = Depends(),
        condition_type: Optional[str] = Query(
            None, description="Filter by condition type"
        ),
        active: Optional[bool] = Query(None, description="Filter by active status"),
    ):
        query = """
            SELECT id, name, condition_type, threshold, strategy_id,
                   implementation_id, notification_channels, is_active, created_at
            FROM alert_rules
            WHERE ($1::text IS NULL OR condition_type = $1)
              AND ($2::boolean IS NULL OR is_active = $2)
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """
        count_query = """
            SELECT COUNT(*) FROM alert_rules
            WHERE ($1::text IS NULL OR condition_type = $1)
              AND ($2::boolean IS NULL OR is_active = $2)
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                query, condition_type, active, pagination.limit, pagination.offset
            )
            total = await conn.fetchval(count_query, condition_type, active)

        items = [_row_to_dict(row) for row in rows]
        return collection_response(
            items,
            "alert_rule",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @alerts_router.get("/{rule_id}")
    async def get_alert_rule(rule_id: str):
        query = """
            SELECT id, name, condition_type, threshold, strategy_id,
                   implementation_id, notification_channels, is_active, created_at
            FROM alert_rules
            WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, rule_id)
        if not row:
            return not_found("AlertRule", rule_id)
        item = _row_to_dict(row)
        return success_response(item, "alert_rule", resource_id=item["id"])

    @alerts_router.put("/{rule_id}")
    async def update_alert_rule(rule_id: str, body: AlertRuleUpdate):
        if (
            body.condition_type is not None
            and body.condition_type not in VALID_CONDITION_TYPES
        ):
            return validation_error(
                f"Invalid condition_type '{body.condition_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_CONDITION_TYPES))}"
            )

        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.condition_type is not None:
            updates["condition_type"] = body.condition_type
        if body.threshold is not None:
            updates["threshold"] = body.threshold
        if body.strategy_id is not None:
            updates["strategy_id"] = body.strategy_id
        if body.implementation_id is not None:
            updates["implementation_id"] = body.implementation_id
        if body.notification_channels is not None:
            updates["notification_channels"] = body.notification_channels
        if body.is_active is not None:
            updates["is_active"] = body.is_active

        if not updates:
            return validation_error("No fields to update")

        set_clauses = []
        params = [rule_id]
        for i, (col, val) in enumerate(updates.items(), start=2):
            cast = ""
            if col in ("strategy_id", "implementation_id"):
                cast = "::uuid"
            set_clauses.append(f"{col} = ${i}{cast}")
            params.append(val)

        query = f"""
            UPDATE alert_rules
            SET {', '.join(set_clauses)}
            WHERE id = $1::uuid
            RETURNING id, name, condition_type, threshold, strategy_id,
                      implementation_id, notification_channels, is_active, created_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
        if not row:
            return not_found("AlertRule", rule_id)
        item = _row_to_dict(row)
        return success_response(item, "alert_rule", resource_id=item["id"])

    @alerts_router.delete("/{rule_id}", status_code=204)
    async def delete_alert_rule(rule_id: str):
        query = "DELETE FROM alert_rules WHERE id = $1::uuid RETURNING id"
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, rule_id)
        if not row:
            return not_found("AlertRule", rule_id)
        return None

    @alerts_router.get("/{rule_id}/history")
    async def get_alert_history(
        rule_id: str,
        pagination: PaginationParams = Depends(),
    ):
        # Verify rule exists
        async with db_pool.acquire() as conn:
            rule = await conn.fetchrow(
                "SELECT id FROM alert_rules WHERE id = $1::uuid", rule_id
            )
            if not rule:
                return not_found("AlertRule", rule_id)

            query = """
                SELECT id, rule_id, triggered_value, message, metadata,
                       acknowledged, acknowledged_at, created_at
                FROM alert_history
                WHERE rule_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """
            count_query = """
                SELECT COUNT(*) FROM alert_history WHERE rule_id = $1::uuid
            """
            rows = await conn.fetch(
                query, rule_id, pagination.limit, pagination.offset
            )
            total = await conn.fetchval(count_query, rule_id)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["rule_id"] = str(item["rule_id"])
            if item.get("triggered_value") is not None:
                item["triggered_value"] = float(item["triggered_value"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("acknowledged_at"):
                item["acknowledged_at"] = item["acknowledged_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "alert_history",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(alerts_router)
    return app


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert an asyncpg Record to a serializable dict."""
    item = dict(row)
    item["id"] = str(item["id"])
    if item.get("strategy_id"):
        item["strategy_id"] = str(item["strategy_id"])
    if item.get("implementation_id"):
        item["implementation_id"] = str(item["implementation_id"])
    if item.get("threshold") is not None:
        item["threshold"] = float(item["threshold"])
    if item.get("notification_channels"):
        item["notification_channels"] = list(item["notification_channels"])
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    return item
