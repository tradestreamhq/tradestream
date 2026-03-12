"""
Alert Notification REST API — RMM Level 2.

Provides CRUD endpoints for alert rules and alert listing/management.
Alert rules define conditions (signal triggered, position opened/closed,
stop loss hit, take profit hit, risk limit breached) that are evaluated
against live strategy data. Matched conditions produce alert records
with status tracking (created → sent → acknowledged → dismissed).
"""

import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
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


# --- Enums ---


class AlertType(str, Enum):
    SIGNAL_TRIGGERED = "signal_triggered"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    RISK_LIMIT_BREACHED = "risk_limit_breached"


class AlertStatus(str, Enum):
    CREATED = "created"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


# --- Request / Response DTOs ---


class AlertRuleCreate(BaseModel):
    name: str = Field(..., description="Human-readable rule name")
    strategy_id: Optional[str] = Field(
        None, description="Strategy ID to scope this rule (null = all strategies)"
    )
    alert_type: AlertType = Field(..., description="Type of condition to monitor")
    conditions: Dict[str, Any] = Field(
        ..., description="Threshold configuration for the rule"
    )
    enabled: bool = Field(True, description="Whether the rule is active")


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    strategy_id: Optional[str] = None
    alert_type: Optional[AlertType] = None
    conditions: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


# --- Alert Evaluation Logic ---


def evaluate_alert_condition(
    rule_type: str,
    conditions: Dict[str, Any],
    event: Dict[str, Any],
) -> bool:
    """Evaluate whether an event matches a rule's conditions.

    Args:
        rule_type: The alert type string.
        conditions: Threshold/filter dict from the rule.
        event: The incoming event data to evaluate.

    Returns:
        True if the event satisfies the rule conditions.
    """
    event_type = event.get("type")
    if event_type != rule_type:
        return False

    min_confidence = conditions.get("min_confidence")
    if min_confidence is not None:
        if (event.get("confidence") or 0) < min_confidence:
            return False

    threshold = conditions.get("threshold")
    if threshold is not None:
        if (event.get("value") or 0) < threshold:
            return False

    symbols = conditions.get("symbols")
    if symbols is not None:
        if event.get("symbol") not in symbols:
            return False

    return True


def match_rules(
    rules: List[Dict[str, Any]],
    event: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return the subset of rules that match a given event.

    Args:
        rules: List of rule dicts with alert_type, conditions, strategy_id.
        event: The incoming event data.

    Returns:
        List of matching rules.
    """
    matched = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        rule_strategy = rule.get("strategy_id")
        event_strategy = event.get("strategy_id")
        if rule_strategy and rule_strategy != event_strategy:
            continue
        if evaluate_alert_condition(
            rule["alert_type"], rule.get("conditions", {}), event
        ):
            matched.append(rule)
    return matched


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Alert API FastAPI application."""
    app = FastAPI(
        title="Alert Notification API",
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

    rules_router = APIRouter(prefix="/rules", tags=["Alert Rules"])
    alerts_router = APIRouter(tags=["Alerts"])

    # --- Alert Rule endpoints ---

    @rules_router.post("", status_code=201)
    async def create_rule(body: AlertRuleCreate):
        query = """
            INSERT INTO alert_rules
                (name, strategy_id, alert_type, conditions, enabled)
            VALUES ($1, $2::uuid, $3, $4::jsonb, $5)
            RETURNING id, name, strategy_id, alert_type, conditions,
                      enabled, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.name,
                    body.strategy_id,
                    body.alert_type.value,
                    json.dumps(body.conditions),
                    body.enabled,
                )
        except asyncpg.UniqueViolationError:
            return conflict(f"Rule with name '{body.name}' already exists")
        except Exception as e:
            logger.error("Failed to create alert rule: %s", e)
            return server_error(str(e))

        item = _format_rule(row)
        return success_response(
            item, "alert_rule", resource_id=item["id"], status_code=201
        )

    @rules_router.get("")
    async def list_rules(
        pagination: PaginationParams = Depends(),
        strategy_id: Optional[str] = Query(
            None, description="Filter by strategy ID"
        ),
        alert_type: Optional[AlertType] = Query(
            None, description="Filter by alert type"
        ),
        enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    ):
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if strategy_id is not None:
            idx += 1
            conditions.append(f"strategy_id = ${idx}::uuid")
            params.append(strategy_id)

        if alert_type is not None:
            idx += 1
            conditions.append(f"alert_type = ${idx}")
            params.append(alert_type.value)

        if enabled is not None:
            idx += 1
            conditions.append(f"enabled = ${idx}")
            params.append(enabled)

        where = " AND ".join(conditions)

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, name, strategy_id, alert_type, conditions,
                   enabled, created_at
            FROM alert_rules
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM alert_rules WHERE {where}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = [_format_rule(row) for row in rows]
        return collection_response(
            items,
            "alert_rule",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @rules_router.get("/{rule_id}")
    async def get_rule(rule_id: str):
        query = """
            SELECT id, name, strategy_id, alert_type, conditions,
                   enabled, created_at
            FROM alert_rules
            WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, rule_id)
        if not row:
            return not_found("Alert rule", rule_id)
        item = _format_rule(row)
        return success_response(item, "alert_rule", resource_id=item["id"])

    @rules_router.patch("/{rule_id}")
    async def update_rule(rule_id: str, body: AlertRuleUpdate):
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.strategy_id is not None:
            updates["strategy_id"] = body.strategy_id
        if body.alert_type is not None:
            updates["alert_type"] = body.alert_type.value
        if body.conditions is not None:
            updates["conditions"] = json.dumps(body.conditions)
        if body.enabled is not None:
            updates["enabled"] = body.enabled

        if not updates:
            return validation_error("No fields to update")

        set_clauses = []
        params = [rule_id]
        for i, (col, val) in enumerate(updates.items(), start=2):
            cast = ""
            if col == "strategy_id":
                cast = "::uuid"
            elif col == "conditions":
                cast = "::jsonb"
            set_clauses.append(f"{col} = ${i}{cast}")
            params.append(val)

        query = f"""
            UPDATE alert_rules
            SET {', '.join(set_clauses)}
            WHERE id = $1::uuid
            RETURNING id, name, strategy_id, alert_type, conditions,
                      enabled, created_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
        if not row:
            return not_found("Alert rule", rule_id)
        item = _format_rule(row)
        return success_response(item, "alert_rule", resource_id=item["id"])

    @rules_router.delete("/{rule_id}", status_code=204)
    async def delete_rule(rule_id: str):
        query = "DELETE FROM alert_rules WHERE id = $1::uuid RETURNING id"
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, rule_id)
        if not row:
            return not_found("Alert rule", rule_id)
        return None

    # --- Alert endpoints ---

    @alerts_router.get("")
    async def list_alerts(
        pagination: PaginationParams = Depends(),
        alert_type: Optional[AlertType] = Query(
            None, description="Filter by alert type"
        ),
        strategy_id: Optional[str] = Query(
            None, description="Filter by strategy ID"
        ),
        status: Optional[AlertStatus] = Query(
            None, description="Filter by alert status"
        ),
    ):
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if alert_type is not None:
            idx += 1
            conditions.append(f"alert_type = ${idx}")
            params.append(alert_type.value)

        if strategy_id is not None:
            idx += 1
            conditions.append(f"strategy_id = ${idx}::uuid")
            params.append(strategy_id)

        if status is not None:
            idx += 1
            conditions.append(f"status = ${idx}")
            params.append(status.value)

        where = " AND ".join(conditions)

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, rule_id, strategy_id, alert_type, status,
                   message, details, created_at
            FROM alerts
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM alerts WHERE {where}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = [_format_alert(row) for row in rows]
        return collection_response(
            items,
            "alert",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @alerts_router.get("/{alert_id}")
    async def get_alert(alert_id: str):
        query = """
            SELECT id, rule_id, strategy_id, alert_type, status,
                   message, details, created_at
            FROM alerts
            WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, alert_id)
        if not row:
            return not_found("Alert", alert_id)
        item = _format_alert(row)
        return success_response(item, "alert", resource_id=item["id"])

    @alerts_router.patch("/{alert_id}")
    async def update_alert_status(alert_id: str, status: AlertStatus = Query(...)):
        query = """
            UPDATE alerts SET status = $2
            WHERE id = $1::uuid
            RETURNING id, rule_id, strategy_id, alert_type, status,
                      message, details, created_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, alert_id, status.value)
        if not row:
            return not_found("Alert", alert_id)
        item = _format_alert(row)
        return success_response(item, "alert", resource_id=item["id"])

    app.include_router(rules_router)
    app.include_router(alerts_router)
    return app


# --- Formatting helpers ---


def _format_rule(row) -> dict:
    item = dict(row)
    item["id"] = str(item["id"])
    if item.get("strategy_id"):
        item["strategy_id"] = str(item["strategy_id"])
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    return item


def _format_alert(row) -> dict:
    item = dict(row)
    item["id"] = str(item["id"])
    if item.get("rule_id"):
        item["rule_id"] = str(item["rule_id"])
    if item.get("strategy_id"):
        item["strategy_id"] = str(item["strategy_id"])
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    return item
