"""
Configuration Management REST API — RMM Level 2.

Provides endpoints for reading, updating, and validating
TradeStream runtime configuration across namespaces.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from services.config_service.config_service import ConfigService, ConfigValidationError
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class ConfigUpdate(BaseModel):
    """Request body for config updates."""

    values: Dict[str, Any]


class ConfigValidateRequest(BaseModel):
    """Request body for config validation."""

    config: Dict[str, Any]


def create_app(config_service: ConfigService) -> FastAPI:
    """Create the Config API FastAPI application."""
    app = FastAPI(
        title="Config API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/config",
    )
    fastapi_auth_middleware(app)
    app.include_router(create_health_router("config-api"))

    config_router = APIRouter(tags=["Config"])

    @config_router.get("")
    async def get_all_config():
        """Get all configuration with secrets masked."""
        config = config_service.get_all(mask_secrets=True)
        return success_response(config, "config")

    @config_router.get("/schema")
    async def get_schema():
        """Get the configuration schema."""
        schema = config_service.get_schema()
        return success_response(schema, "config_schema")

    @config_router.get("/{namespace}")
    async def get_namespace_config(namespace: str):
        """Get configuration for a specific namespace."""
        data = config_service.get_namespace(namespace, mask_secrets=True)
        if data is None:
            return not_found("Namespace", namespace)
        return success_response(data, "config", resource_id=namespace)

    @config_router.put("/{namespace}")
    async def update_namespace_config(namespace: str, body: ConfigUpdate):
        """Update configuration for a namespace at runtime."""
        try:
            updated = config_service.update_namespace(namespace, body.values)
        except ValueError as e:
            return not_found("Namespace", namespace)
        except ConfigValidationError as e:
            return validation_error("Config validation failed", details=e.errors)
        return success_response(updated, "config", resource_id=namespace)

    @config_router.post("/validate")
    async def validate_config(body: ConfigValidateRequest):
        """Validate a configuration blob."""
        result = config_service.validate_config(body.config)
        return success_response(result, "config_validation")

    app.include_router(config_router)
    return app
