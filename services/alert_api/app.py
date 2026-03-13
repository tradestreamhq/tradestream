"""
Price Alert REST API — RMM Level 2.

Provides endpoints for creating, listing, and managing price alerts,
plus an alert evaluation engine that checks active alerts against
latest prices.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

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


# --- Request / Response DTOs ---


class AlertCreate(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol, e.g. BTC/USD")
    condition: str = Field(
        ...,
        description="Alert condition: above, below, or cross",
        pattern="^(above|below|cross)$",
    )
    target_price: Optional[float] = Field(
        None, description="Absolute target price (required unless percentage is set)"
    )
    percentage: Optional[float] = Field(
        None,
        description="Percentage change from current price (e.g. 5.0 for +5%%)",
    )
    current_price: Optional[float] = Field(
        None,
        description="Current/reference price for percentage-based alerts",
    )
    notification_channel: str = Field(
        "webhook", description="Notification channel: webhook, email, slack"
    )


# --- Helpers ---


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert an asyncpg Record to a JSON-safe dict."""
    item = dict(row)
    for key in (
        "target_price",
        "reference_price",
        "percentage",
        "trigger_price",
        "last_checked_price",
    ):
        if item.get(key) is not None:
            item[key] = float(item[key])
    for key in ("created_at", "updated_at", "triggered_at"):
        if item.get(key) is not None:
            item[key] = item[key].isoformat()
    if item.get("id") is not None:
        item["id"] = str(item["id"])
    return item


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Alert API FastAPI application."""
    app = FastAPI(
        title="Alert API",
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

    # ------------------------------------------------------------------
    # POST / — create a price alert
    # ------------------------------------------------------------------
    @app.post("", tags=["Alerts"], status_code=201)
    async def create_alert(body: AlertCreate):
        """Create a new price alert."""
        # Validate: need either target_price or percentage+current_price
        if body.target_price is None and body.percentage is None:
            return validation_error(
                "Either target_price or percentage must be provided"
            )

        target_price = body.target_price
        reference_price = body.current_price
        percentage = body.percentage

        if body.percentage is not None:
            if body.current_price is None or body.current_price <= 0:
                return validation_error(
                    "current_price is required and must be positive for percentage-based alerts"
                )
            target_price = body.current_price * (1 + body.percentage / 100.0)
            reference_price = body.current_price

        if target_price is not None and target_price <= 0:
            return validation_error("target_price must be positive")

        query = """
            INSERT INTO price_alerts
                (symbol, condition, target_price, reference_price, percentage,
                 notification_channel, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            RETURNING id, symbol, condition, target_price, reference_price,
                      percentage, notification_channel, status,
                      trigger_price, triggered_at, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.symbol,
                    body.condition,
                    target_price,
                    reference_price,
                    percentage,
                    body.notification_channel,
                )
            alert = _row_to_dict(row)
            return success_response(alert, "price_alert", resource_id=alert["id"])
        except Exception as e:
            logger.error("Error creating alert: %s", e)
            return server_error(str(e))

    # ------------------------------------------------------------------
    # GET / — list alerts with optional status filter
    # ------------------------------------------------------------------
    @app.get("", tags=["Alerts"])
    async def list_alerts(
        status: Optional[str] = Query(
            None,
            description="Filter by status: active, triggered, expired, cancelled",
        ),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        limit: int = Query(50, ge=1, le=200, description="Max results"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
    ):
        """List price alerts with optional filters."""
        conditions = []
        params: list = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM price_alerts {where}"
        query = f"""
            SELECT id, symbol, condition, target_price, reference_price,
                   percentage, notification_channel, status,
                   trigger_price, triggered_at, last_checked_price,
                   created_at, updated_at
            FROM price_alerts {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        try:
            async with db_pool.acquire() as conn:
                total = await conn.fetchval(count_query, *params[:-2])
                rows = await conn.fetch(query, *params)
            items = [_row_to_dict(r) for r in rows]
            return collection_response(
                items, "price_alert", total=total, limit=limit, offset=offset
            )
        except Exception as e:
            logger.error("Error listing alerts: %s", e)
            return server_error(str(e))

    # ------------------------------------------------------------------
    # DELETE /{alert_id} — cancel an alert
    # ------------------------------------------------------------------
    @app.delete("/{alert_id}", tags=["Alerts"])
    async def cancel_alert(alert_id: str):
        """Cancel an active alert."""
        query = """
            UPDATE price_alerts
            SET status = 'cancelled'
            WHERE id = $1 AND status = 'active'
            RETURNING id
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, alert_id)
            if not row:
                return not_found("Alert", alert_id)
            return success_response(
                {"id": alert_id, "status": "cancelled"},
                "price_alert",
                resource_id=alert_id,
            )
        except Exception as e:
            logger.error("Error cancelling alert: %s", e)
            return server_error(str(e))

    # ------------------------------------------------------------------
    # GET /history — triggered alerts
    # ------------------------------------------------------------------
    @app.get("/history", tags=["Alerts"])
    async def alert_history(
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        limit: int = Query(50, ge=1, le=200, description="Max results"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
    ):
        """Get history of triggered alerts with timestamps and trigger prices."""
        conditions = ["status = 'triggered'"]
        params: list = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}"

        count_query = f"SELECT COUNT(*) FROM price_alerts {where}"
        query = f"""
            SELECT id, symbol, condition, target_price, reference_price,
                   percentage, notification_channel, status,
                   trigger_price, triggered_at, created_at, updated_at
            FROM price_alerts {where}
            ORDER BY triggered_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        try:
            async with db_pool.acquire() as conn:
                total = await conn.fetchval(count_query, *params[:-2])
                rows = await conn.fetch(query, *params)
            items = [_row_to_dict(r) for r in rows]
            return collection_response(
                items, "price_alert", total=total, limit=limit, offset=offset
            )
        except Exception as e:
            logger.error("Error fetching alert history: %s", e)
            return server_error(str(e))

    # ------------------------------------------------------------------
    # POST /evaluate — run alert evaluation engine
    # ------------------------------------------------------------------
    @app.post("/evaluate", tags=["Engine"])
    async def evaluate_alerts(
        prices: Optional[Dict[str, float]] = None,
    ):
        """Evaluate all active alerts against provided or latest prices.

        Accepts a JSON body mapping symbol -> current_price.
        Returns a list of newly triggered alerts.
        """
        if not prices:
            return validation_error("prices map (symbol -> price) is required")

        triggered = await run_evaluation(db_pool, prices)
        return success_response(
            {"triggered_count": len(triggered), "triggered": triggered},
            "evaluation_result",
        )

    return app


# ------------------------------------------------------------------
# Alert Evaluation Engine
# ------------------------------------------------------------------


async def run_evaluation(
    db_pool: asyncpg.Pool, prices: Dict[str, float]
) -> List[Dict[str, Any]]:
    """Check active alerts against latest prices and trigger matches.

    Args:
        db_pool: asyncpg connection pool.
        prices: Mapping of symbol -> current price.

    Returns:
        List of triggered alert dicts.
    """
    if not prices:
        return []

    symbols = list(prices.keys())
    query = """
        SELECT id, symbol, condition, target_price, last_checked_price
        FROM price_alerts
        WHERE status = 'active' AND symbol = ANY($1)
    """

    triggered_alerts: List[Dict[str, Any]] = []

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, symbols)

        for row in rows:
            alert_id = row["id"]
            symbol = row["symbol"]
            condition = row["condition"]
            target = float(row["target_price"])
            last_price = (
                float(row["last_checked_price"]) if row["last_checked_price"] else None
            )
            current = prices[symbol]

            should_trigger = _check_condition(condition, target, current, last_price)

            if should_trigger:
                trigger_query = """
                    UPDATE price_alerts
                    SET status = 'triggered',
                        trigger_price = $1,
                        triggered_at = NOW(),
                        last_checked_price = $1
                    WHERE id = $2 AND status = 'active'
                    RETURNING id, symbol, condition, target_price, trigger_price,
                              triggered_at, notification_channel
                """
                triggered_row = await conn.fetchrow(trigger_query, current, alert_id)
                if triggered_row:
                    triggered_alerts.append(_row_to_dict(triggered_row))
            else:
                # Update last_checked_price for cross detection
                await conn.execute(
                    "UPDATE price_alerts SET last_checked_price = $1 WHERE id = $2",
                    current,
                    alert_id,
                )

    return triggered_alerts


def _check_condition(
    condition: str,
    target: float,
    current: float,
    last_price: Optional[float],
) -> bool:
    """Determine whether an alert condition is met.

    Args:
        condition: One of 'above', 'below', 'cross'.
        target: The target price for the alert.
        current: The current market price.
        last_price: The previously checked price (for cross detection).

    Returns:
        True if the alert should trigger.
    """
    if condition == "above":
        return current >= target
    elif condition == "below":
        return current <= target
    elif condition == "cross":
        if last_price is None:
            return False
        crossed_up = last_price < target and current >= target
        crossed_down = last_price > target and current <= target
        return crossed_up or crossed_down
    return False
