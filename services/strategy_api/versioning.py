"""
Strategy versioning and audit trail.

Provides version tracking for strategy specs, including snapshot creation,
restore, and diff capabilities.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)

logger = logging.getLogger(__name__)


# --- DTOs ---


class RestoreRequest(BaseModel):
    change_description: Optional[str] = Field(
        None, description="Reason for restoring this version"
    )


# --- Diff Utility ---


def diff_configs(
    old: Dict[str, Any], new: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Compare two config snapshots and return a list of changes.

    Each change has: field, action (added/removed/modified), old_value, new_value.
    """
    changes: List[Dict[str, Any]] = []
    all_keys = set(old.keys()) | set(new.keys())

    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)

        if key not in old:
            changes.append(
                {"field": key, "action": "added", "old_value": None, "new_value": new_val}
            )
        elif key not in new:
            changes.append(
                {"field": key, "action": "removed", "old_value": old_val, "new_value": None}
            )
        elif old_val != new_val:
            # For nested dicts, recurse to show detailed changes
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                nested = diff_configs(old_val, new_val)
                for change in nested:
                    change["field"] = f"{key}.{change['field']}"
                    changes.append(change)
            else:
                changes.append(
                    {
                        "field": key,
                        "action": "modified",
                        "old_value": old_val,
                        "new_value": new_val,
                    }
                )

    return changes


# --- Helper Functions ---


async def _get_spec(conn: asyncpg.Connection, spec_id: str) -> Optional[asyncpg.Record]:
    """Fetch a strategy spec by ID."""
    return await conn.fetchrow(
        """
        SELECT id, name, indicators, entry_conditions, exit_conditions,
               parameters, description, source, created_at
        FROM strategy_specs WHERE id = $1::uuid
        """,
        spec_id,
    )


def _spec_to_snapshot(spec: dict) -> Dict[str, Any]:
    """Extract the config fields from a spec record into a snapshot dict."""
    return {
        "name": spec.get("name"),
        "indicators": spec.get("indicators"),
        "entry_conditions": spec.get("entry_conditions"),
        "exit_conditions": spec.get("exit_conditions"),
        "parameters": spec.get("parameters"),
        "description": spec.get("description"),
    }


async def create_version_snapshot(
    conn: asyncpg.Connection,
    spec_id: str,
    change_description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[asyncpg.Record]:
    """Create a new version snapshot from the current state of a strategy spec.

    Returns the newly created version record, or None if the spec doesn't exist.
    """
    spec = await _get_spec(conn, spec_id)
    if not spec:
        return None

    snapshot = _spec_to_snapshot(dict(spec))

    # Get next version number
    max_version = await conn.fetchval(
        "SELECT COALESCE(MAX(version_number), 0) FROM strategy_versions WHERE strategy_id = $1::uuid",
        spec_id,
    )
    next_version = max_version + 1

    row = await conn.fetchrow(
        """
        INSERT INTO strategy_versions
            (strategy_id, version_number, config_snapshot, change_description, created_by)
        VALUES ($1::uuid, $2, $3::jsonb, $4, $5)
        RETURNING id, strategy_id, version_number, config_snapshot,
                  change_description, created_by, created_at
        """,
        spec_id,
        next_version,
        json.dumps(snapshot),
        change_description,
        created_by,
    )
    return row


# --- Router Factory ---


def create_versioning_router(db_pool: asyncpg.Pool) -> APIRouter:
    """Create the versioning sub-router for strategy specs."""
    router = APIRouter(
        prefix="/specs/{spec_id}/versions",
        tags=["Versioning"],
    )

    @router.get("")
    async def list_versions(
        spec_id: str,
        pagination: PaginationParams = Depends(),
    ):
        """List all versions for a strategy spec."""
        async with db_pool.acquire() as conn:
            # Verify spec exists
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", spec_id
            )
            if not spec:
                return not_found("Spec", spec_id)

            rows = await conn.fetch(
                """
                SELECT id, strategy_id, version_number, config_snapshot,
                       change_description, created_by, created_at
                FROM strategy_versions
                WHERE strategy_id = $1::uuid
                ORDER BY version_number DESC
                LIMIT $2 OFFSET $3
                """,
                spec_id,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM strategy_versions WHERE strategy_id = $1::uuid",
                spec_id,
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "strategy_version",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @router.get("/diff")
    async def diff_versions(
        spec_id: str,
        v1: int = Query(..., description="First version number"),
        v2: int = Query(..., description="Second version number"),
    ):
        """Diff two versions of a strategy spec."""
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", spec_id
            )
            if not spec:
                return not_found("Spec", spec_id)

            row1 = await conn.fetchrow(
                """
                SELECT config_snapshot FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                spec_id,
                v1,
            )
            row2 = await conn.fetchrow(
                """
                SELECT config_snapshot FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                spec_id,
                v2,
            )

        if not row1:
            return not_found("Version", str(v1))
        if not row2:
            return not_found("Version", str(v2))

        old_config = row1["config_snapshot"]
        new_config = row2["config_snapshot"]

        # asyncpg returns JSONB as dicts directly
        if isinstance(old_config, str):
            old_config = json.loads(old_config)
        if isinstance(new_config, str):
            new_config = json.loads(new_config)

        changes = diff_configs(old_config, new_config)

        return success_response(
            {
                "strategy_id": spec_id,
                "from_version": v1,
                "to_version": v2,
                "changes": changes,
            },
            "version_diff",
        )

    @router.get("/{version_number}")
    async def get_version(spec_id: str, version_number: int):
        """Get a specific version of a strategy spec."""
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", spec_id
            )
            if not spec:
                return not_found("Spec", spec_id)

            row = await conn.fetchrow(
                """
                SELECT id, strategy_id, version_number, config_snapshot,
                       change_description, created_by, created_at
                FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                spec_id,
                version_number,
            )

        if not row:
            return not_found("Version", str(version_number))

        item = dict(row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

        return success_response(item, "strategy_version", resource_id=item["id"])

    @router.post("/{version_number}/restore")
    async def restore_version(
        spec_id: str,
        version_number: int,
        body: Optional[RestoreRequest] = None,
    ):
        """Restore a strategy spec to a previous version.

        This updates the spec with the config from the specified version
        and creates a new version entry documenting the restore.
        """
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", spec_id
            )
            if not spec:
                return not_found("Spec", spec_id)

            version_row = await conn.fetchrow(
                """
                SELECT config_snapshot FROM strategy_versions
                WHERE strategy_id = $1::uuid AND version_number = $2
                """,
                spec_id,
                version_number,
            )
            if not version_row:
                return not_found("Version", str(version_number))

            snapshot = version_row["config_snapshot"]
            if isinstance(snapshot, str):
                snapshot = json.loads(snapshot)

            # Update the strategy spec with the restored config
            await conn.execute(
                """
                UPDATE strategy_specs
                SET name = $2,
                    indicators = $3::jsonb,
                    entry_conditions = $4::jsonb,
                    exit_conditions = $5::jsonb,
                    parameters = $6::jsonb,
                    description = $7
                WHERE id = $1::uuid
                """,
                spec_id,
                snapshot.get("name"),
                json.dumps(snapshot.get("indicators", {})),
                json.dumps(snapshot.get("entry_conditions", {})),
                json.dumps(snapshot.get("exit_conditions", {})),
                json.dumps(snapshot.get("parameters", {})),
                snapshot.get("description"),
            )

            # Create a new version recording the restore
            change_desc = (
                body.change_description
                if body and body.change_description
                else f"Restored to version {version_number}"
            )
            new_version = await create_version_snapshot(
                conn, spec_id, change_description=change_desc
            )

        if not new_version:
            return server_error("Failed to create restore version snapshot")

        item = dict(new_version)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

        return success_response(item, "strategy_version", resource_id=item["id"])

    return router
