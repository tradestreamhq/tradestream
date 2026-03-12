"""FastAPI application for the alert routing service."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI

from services.alert_router.models import Alert, RouteConfig
from services.alert_router.router import AlertRouter
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)

REQUIRED_CHANNEL_FIELDS = {"channel_type", "name"}


def create_app(alert_router: Optional[AlertRouter] = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Alert Router Service", version="1.0.0")
    router_instance = alert_router or AlertRouter()

    health_router = create_health_router("alert-router")
    app.include_router(health_router)

    api_router = APIRouter(prefix="/api/v1/alerts", tags=["Alert Routing"])

    @api_router.post("/route-config")
    async def upsert_route_config(body: Dict[str, Any]):
        """Create or update a user's routing configuration."""
        if "user_id" not in body:
            return validation_error("user_id is required")

        channels = body.get("channels", [])
        for ch in channels:
            missing = REQUIRED_CHANNEL_FIELDS - set(ch.keys())
            if missing:
                return validation_error(
                    f"Channel missing required fields: {missing}"
                )
            valid_types = {"email", "slack_webhook", "custom_webhook", "in_app"}
            if ch.get("channel_type") not in valid_types:
                return validation_error(
                    f"Invalid channel_type: {ch.get('channel_type')}. "
                    f"Must be one of: {valid_types}"
                )

        try:
            config = RouteConfig.from_dict(body)
        except (KeyError, ValueError) as e:
            return validation_error(f"Invalid config: {e}")

        router_instance.set_route_config(config)
        return success_response(
            data=config.to_dict(),
            resource_type="route_config",
            resource_id=config.user_id,
            status_code=200,
        )

    @api_router.get("/route-config/{user_id}")
    async def get_route_config(user_id: str):
        """Get a user's routing configuration."""
        config = router_instance.get_route_config(user_id)
        if not config:
            return not_found("RouteConfig", user_id)
        return success_response(
            data=config.to_dict(),
            resource_type="route_config",
            resource_id=user_id,
        )

    @api_router.delete("/route-config/{user_id}")
    async def delete_route_config(user_id: str):
        """Delete a user's routing configuration."""
        deleted = router_instance.delete_route_config(user_id)
        if not deleted:
            return not_found("RouteConfig", user_id)
        return success_response(
            data={"deleted": True},
            resource_type="route_config",
            resource_id=user_id,
        )

    @api_router.post("/route")
    async def route_alert(body: Dict[str, Any]):
        """Route an alert to configured channels."""
        for field in ("alert_type", "title", "message", "user_id"):
            if field not in body:
                return validation_error(f"{field} is required")

        alert = Alert(
            alert_type=body["alert_type"],
            title=body["title"],
            message=body["message"],
            user_id=body["user_id"],
            metadata=body.get("metadata", {}),
        )
        records = router_instance.route_alert(alert)
        return success_response(
            data={
                "alert_id": alert.alert_id,
                "deliveries": [r.to_dict() for r in records],
            },
            resource_type="alert_delivery",
            resource_id=alert.alert_id,
        )

    @api_router.get("/history")
    async def get_history(
        user_id: Optional[str] = None,
        alert_id: Optional[str] = None,
        pagination: PaginationParams = Depends(),
    ):
        """Get alert delivery history."""
        records = router_instance.get_delivery_history(
            user_id=user_id,
            alert_id=alert_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        total = router_instance.get_history_count(
            user_id=user_id, alert_id=alert_id
        )
        return collection_response(
            items=[r.to_dict() for r in records],
            resource_type="delivery_record",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(api_router)
    return app
