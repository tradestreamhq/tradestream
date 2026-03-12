"""
Strategy Versioning REST API — RMM Level 2.

Tracks parameter changes to strategy specs and supports rollback.
"""

import json
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query

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
from services.strategy_versioning_api.models import RollbackRequest

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Versioning API FastAPI application."""
    app = FastAPI(
        title="Strategy Versioning API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategy-versions",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-versioning-api", check_deps))

    router = APIRouter(prefix="/strategies", tags=["Versioning"])

    @router.get("/{strategy_id}/versions")
    async def list_versions(
        strategy_id: str,
        pagination: PaginationParams = Depends(),
    ):
        """List all versions for a strategy spec, newest first."""
        # Verify strategy exists
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", strategy_id
            )
            if not spec:
                return not_found("Strategy", strategy_id)

            rows = await conn.fetch(
                """
                SELECT id, strategy_id, version_number, parameters, indicators,
                       entry_conditions, exit_conditions, changed_by, changed_at,
                       change_reason
                FROM strategy_versions
                WHERE strategy_id = $1::uuid
                ORDER BY version_number DESC
                LIMIT $2 OFFSET $3
                """,
                strategy_id,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM strategy_versions WHERE strategy_id = $1::uuid",
                strategy_id,
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            if item.get("changed_at"):
                item["changed_at"] = item["changed_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "strategy_version",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @router.get("/{strategy_id}/versions/{version_number}")
    async def get_version(strategy_id: str, version_number: int):
        """Get a specific version of a strategy."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, strategy_id, version_number, parameters, indicators,
                       entry_conditions, exit_conditions, changed_by, changed_at,
                       change_reason
                FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                strategy_id,
                version_number,
            )
        if not row:
            return not_found("Version", f"{strategy_id}/v{version_number}")
        item = dict(row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("changed_at"):
            item["changed_at"] = item["changed_at"].isoformat()
        return success_response(item, "strategy_version", resource_id=item["id"])

    @router.get("/{strategy_id}/versions/{version_a}/diff/{version_b}")
    async def diff_versions(strategy_id: str, version_a: int, version_b: int):
        """Show differences between two versions of a strategy."""
        async with db_pool.acquire() as conn:
            row_a = await conn.fetchrow(
                """
                SELECT version_number, parameters, indicators,
                       entry_conditions, exit_conditions
                FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                strategy_id,
                version_a,
            )
            row_b = await conn.fetchrow(
                """
                SELECT version_number, parameters, indicators,
                       entry_conditions, exit_conditions
                FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                strategy_id,
                version_b,
            )

        if not row_a:
            return not_found("Version", f"{strategy_id}/v{version_a}")
        if not row_b:
            return not_found("Version", f"{strategy_id}/v{version_b}")

        fields = ["parameters", "indicators", "entry_conditions", "exit_conditions"]
        changes = {}
        for field in fields:
            val_a = row_a[field]
            val_b = row_b[field]
            if val_a != val_b:
                changes[field] = {"before": val_a, "after": val_b}

        return success_response(
            {
                "strategy_id": strategy_id,
                "version_a": version_a,
                "version_b": version_b,
                "changes": changes,
            },
            "version_diff",
        )

    @router.post("/{strategy_id}/rollback/{version_number}")
    async def rollback_to_version(
        strategy_id: str,
        version_number: int,
        body: RollbackRequest,
    ):
        """Rollback a strategy to a previous version.

        Restores the strategy spec's parameters, indicators, and conditions
        from the specified version and creates a new version record.
        """
        async with db_pool.acquire() as conn:
            # Get the target version
            target = await conn.fetchrow(
                """
                SELECT parameters, indicators, entry_conditions, exit_conditions
                FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                strategy_id,
                version_number,
            )
            if not target:
                return not_found("Version", f"{strategy_id}/v{version_number}")

            # Get current max version number
            max_version = await conn.fetchval(
                "SELECT COALESCE(MAX(version_number), 0) FROM strategy_versions WHERE strategy_id = $1::uuid",
                strategy_id,
            )
            new_version = max_version + 1

            reason = body.change_reason or f"Rollback to version {version_number}"

            # Apply rollback in a transaction
            async with conn.transaction():
                # Update the strategy spec
                await conn.execute(
                    """
                    UPDATE strategy_specs
                    SET parameters = $2::jsonb,
                        indicators = $3::jsonb,
                        entry_conditions = $4::jsonb,
                        exit_conditions = $5::jsonb
                    WHERE id = $1::uuid
                    """,
                    strategy_id,
                    json.dumps(target["parameters"]) if isinstance(target["parameters"], dict) else target["parameters"],
                    json.dumps(target["indicators"]) if isinstance(target["indicators"], dict) else target["indicators"],
                    json.dumps(target["entry_conditions"]) if isinstance(target["entry_conditions"], dict) else target["entry_conditions"],
                    json.dumps(target["exit_conditions"]) if isinstance(target["exit_conditions"], dict) else target["exit_conditions"],
                )

                # Create a new version record for the rollback
                row = await conn.fetchrow(
                    """
                    INSERT INTO strategy_versions
                        (strategy_id, version_number, parameters, indicators,
                         entry_conditions, exit_conditions, changed_by, change_reason)
                    VALUES ($1::uuid, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6::jsonb, $7, $8)
                    RETURNING id, strategy_id, version_number, parameters, indicators,
                              entry_conditions, exit_conditions, changed_by, changed_at,
                              change_reason
                    """,
                    strategy_id,
                    new_version,
                    json.dumps(target["parameters"]) if isinstance(target["parameters"], dict) else target["parameters"],
                    json.dumps(target["indicators"]) if isinstance(target["indicators"], dict) else target["indicators"],
                    json.dumps(target["entry_conditions"]) if isinstance(target["entry_conditions"], dict) else target["entry_conditions"],
                    json.dumps(target["exit_conditions"]) if isinstance(target["exit_conditions"], dict) else target["exit_conditions"],
                    body.changed_by,
                    reason,
                )

        item = dict(row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("changed_at"):
            item["changed_at"] = item["changed_at"].isoformat()
        return success_response(
            item, "strategy_version", resource_id=item["id"], status_code=201
        )

    app.include_router(router)
    return app
