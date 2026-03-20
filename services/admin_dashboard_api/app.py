"""
Admin Dashboard REST API — RMM Level 2.

Provides endpoints for user management, system health,
audit logs, and platform metrics. Requires admin role.
"""

import logging
import os
import platform
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "trader", "viewer"}


# --- Request DTOs ---


class RoleUpdate(BaseModel):
    role: str = Field(..., description="New role: admin, trader, or viewer")


class StatusUpdate(BaseModel):
    is_active: bool = Field(..., description="Whether the user is active")


# --- Admin role dependency ---


async def require_admin(x_admin_user_id: str = Header(..., alias="X-Admin-User-Id")):
    """Validate that the requesting user has admin role.

    The caller must supply X-Admin-User-Id header. The actual role check
    happens inside each endpoint against the database.
    """
    return x_admin_user_id


# --- Audit log helper ---


async def _record_audit(
    conn,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    await conn.execute(
        """
        INSERT INTO audit_logs (user_id, action, resource_type, resource_id, changes, ip_address)
        VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6)
        """,
        user_id,
        action,
        resource_type,
        resource_id,
        _json_str(changes) if changes else None,
        ip_address,
    )


def _json_str(obj):
    import json

    return json.dumps(obj)


def _get_memory_info() -> Dict[str, Any]:
    """Read memory info from /proc/meminfo (Linux) or return empty on other OS."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        meminfo = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip().split()[0]  # value in kB
                meminfo[key] = int(val)
        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", 0)
        used_kb = total_kb - available_kb
        total_mb = round(total_kb / 1024, 1)
        used_mb = round(used_kb / 1024, 1)
        percent = round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0.0
        return {"total_mb": total_mb, "used_mb": used_mb, "percent": percent}
    except (OSError, ValueError):
        return {"total_mb": 0, "used_mb": 0, "percent": 0}


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Admin Dashboard API FastAPI application."""
    app = FastAPI(
        title="Admin Dashboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/admin",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("admin-dashboard-api", check_deps))

    # --- Middleware to verify admin role ---

    async def _verify_admin(admin_user_id: str):
        """Check that the user exists and has admin role. Returns the user row."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, username, role, is_active FROM users WHERE id = $1::uuid",
                admin_user_id,
            )
        if not row:
            return None, "Admin user not found"
        if dict(row)["role"] != "admin":
            return None, "Insufficient permissions: admin role required"
        if not dict(row)["is_active"]:
            return None, "Admin account is deactivated"
        return dict(row), None

    # ======================================================================
    # Users endpoints
    # ======================================================================

    users_router = APIRouter(prefix="/users", tags=["Users"])

    @users_router.get("")
    async def list_users(
        pagination: PaginationParams = Depends(),
        admin_user_id: str = Depends(require_admin),
    ):
        """List all users with stats."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, username, email, role, is_active, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM users")

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
            items.append(item)

        return collection_response(
            items, "user", total=total, limit=pagination.limit, offset=pagination.offset
        )

    @users_router.put("/{user_id}/role")
    async def update_user_role(
        user_id: str,
        body: RoleUpdate,
        request: Request,
        admin_user_id: str = Depends(require_admin),
    ):
        """Change a user's role."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        if body.role not in VALID_ROLES:
            return validation_error(
                f"Invalid role '{body.role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}"
            )

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE users SET role = $1 WHERE id = $2::uuid
                RETURNING id, username, email, role, is_active, created_at, updated_at
                """,
                body.role,
                user_id,
            )
            if not row:
                return not_found("User", user_id)

            await _record_audit(
                conn,
                admin_user_id,
                "update_role",
                "user",
                user_id,
                {"role": body.role},
                request.client.host if request.client else None,
            )

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "user", resource_id=item["id"])

    @users_router.put("/{user_id}/status")
    async def update_user_status(
        user_id: str,
        body: StatusUpdate,
        request: Request,
        admin_user_id: str = Depends(require_admin),
    ):
        """Activate or deactivate a user."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE users SET is_active = $1 WHERE id = $2::uuid
                RETURNING id, username, email, role, is_active, created_at, updated_at
                """,
                body.is_active,
                user_id,
            )
            if not row:
                return not_found("User", user_id)

            await _record_audit(
                conn,
                admin_user_id,
                "update_status",
                "user",
                user_id,
                {"is_active": body.is_active},
                request.client.host if request.client else None,
            )

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "user", resource_id=item["id"])

    app.include_router(users_router)

    # ======================================================================
    # System health endpoint
    # ======================================================================

    @app.get("/system", tags=["System"])
    async def get_system_health(admin_user_id: str = Depends(require_admin)):
        """System health: active strategies, open positions, DB connections, memory."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        async with db_pool.acquire() as conn:
            active_strategies = await conn.fetchval(
                "SELECT COUNT(*) FROM strategy_specs WHERE is_active = TRUE"
            )
            open_positions = await conn.fetchval(
                "SELECT COUNT(*) FROM paper_portfolio WHERE quantity != 0"
            )
            db_connections = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )

        memory_info = _get_memory_info()

        return success_response(
            {
                "active_strategies": active_strategies,
                "open_positions": open_positions,
                "db_connections": db_connections,
                "memory": memory_info,
                "platform": platform.platform(),
            },
            "system_health",
        )

    # ======================================================================
    # Audit log endpoint
    # ======================================================================

    @app.get("/audit-log", tags=["Audit"])
    async def get_audit_log(
        pagination: PaginationParams = Depends(),
        admin_user_id: str = Depends(require_admin),
    ):
        """Recent admin actions."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT al.id, al.user_id, u.username, al.action, al.resource_type,
                       al.resource_id, al.changes, al.ip_address, al.created_at
                FROM audit_logs al
                JOIN users u ON u.id = al.user_id
                ORDER BY al.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM audit_logs")

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["user_id"] = str(item["user_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "audit_log",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # ======================================================================
    # Platform metrics endpoint
    # ======================================================================

    @app.get("/metrics", tags=["Metrics"])
    async def get_metrics(admin_user_id: str = Depends(require_admin)):
        """Platform-wide metrics: total trades, active users, revenue."""
        admin, err = await _verify_admin(admin_user_id)
        if err:
            return error_response("FORBIDDEN", err, status_code=403)

        async with db_pool.acquire() as conn:
            total_trades = await conn.fetchval("SELECT COUNT(*) FROM paper_trades")
            open_trades = await conn.fetchval(
                "SELECT COUNT(*) FROM paper_trades WHERE status = 'OPEN'"
            )
            closed_trades = await conn.fetchval(
                "SELECT COUNT(*) FROM paper_trades WHERE status = 'CLOSED'"
            )
            active_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE"
            )
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            revenue_row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(pnl), 0) as total_pnl,
                       COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0) as gross_profit,
                       COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0) as gross_loss
                FROM paper_trades
                WHERE status = 'CLOSED'
                """
            )

        rev = dict(revenue_row) if revenue_row else {}

        return success_response(
            {
                "total_trades": total_trades,
                "open_trades": open_trades,
                "closed_trades": closed_trades,
                "active_users": active_users,
                "total_users": total_users,
                "revenue": {
                    "total_pnl": float(rev.get("total_pnl", 0)),
                    "gross_profit": float(rev.get("gross_profit", 0)),
                    "gross_loss": float(rev.get("gross_loss", 0)),
                },
            },
            "platform_metrics",
        )

    return app
