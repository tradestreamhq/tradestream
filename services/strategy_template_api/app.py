"""
Strategy Template Library REST API.

Provides endpoints for browsing and instantiating pre-built strategy
templates into custom strategy specs.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.strategy_template_api.templates import (
    get_template,
    instantiate_template,
    list_templates,
)

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class InstantiateRequest(BaseModel):
    name: str = Field(..., description="Name for the new strategy instance")
    parameter_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values to override template defaults",
    )


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Template API FastAPI application."""
    app = FastAPI(
        title="Strategy Template Library API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategy-templates",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-template-api", check_deps))

    router = APIRouter(tags=["Strategy Templates"])

    @router.get("")
    async def list_strategy_templates(
        category: Optional[str] = Query(
            None, description="Filter by category (e.g. trend-following, mean-reversion)"
        ),
    ):
        templates = list_templates(category=category)
        items = []
        for t in templates:
            items.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "category": t["category"],
                    "complexity": t["complexity"],
                    "recommended_markets": t["recommended_markets"],
                    "risk_profile": t["risk_profile"],
                }
            )
        return collection_response(items, "strategy_template", total=len(items))

    @router.get("/{template_id}")
    async def get_strategy_template(template_id: str):
        template = get_template(template_id)
        if template is None:
            return not_found("Template", template_id)
        return success_response(
            template, "strategy_template", resource_id=template["id"]
        )

    @router.post("/{template_id}/instantiate", status_code=201)
    async def instantiate_strategy_template(
        template_id: str, body: InstantiateRequest
    ):
        template = get_template(template_id)
        if template is None:
            return not_found("Template", template_id)

        config = instantiate_template(
            template_id,
            overrides=body.parameter_overrides,
            name_override=body.name,
        )

        query = """
            INSERT INTO strategy_specs
                (name, indicators, entry_conditions, exit_conditions,
                 parameters, description, source)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6, 'TEMPLATE')
            RETURNING id, name, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    config["name"],
                    json.dumps(config["indicators"]),
                    json.dumps(config["entryConditions"]),
                    json.dumps(config["exitConditions"]),
                    json.dumps(config["parameters"]),
                    template["description"],
                )
        except asyncpg.UniqueViolationError:
            return conflict(f"Strategy with name '{config['name']}' already exists")
        except Exception as e:
            logger.error("Failed to instantiate template: %s", e)
            return server_error(str(e))

        return success_response(
            data={
                "name": config["name"],
                "template_id": template_id,
                "indicators": config["indicators"],
                "entry_conditions": config["entryConditions"],
                "exit_conditions": config["exitConditions"],
                "parameters": config["parameters"],
                "description": template["description"],
            },
            resource_type="strategy_spec",
            resource_id=str(row["id"]),
            status_code=201,
        )

    app.include_router(router)
    return app
