"""
Standard health check endpoints for all REST API services.
"""

from fastapi import APIRouter

from services.shared.monitoring import (
    DEPENDENCY_UP,
    SERVICE_UP,
    build_health_response,
)

router = APIRouter(tags=["Health"])


def create_health_router(service_name: str, check_fn=None) -> APIRouter:
    """Create a health router with /health and /ready endpoints.

    Args:
        service_name: Name of the service for identification.
        check_fn: Optional async callable returning dict of dependency statuses.
    """
    health_router = APIRouter(tags=["Health"])

    @health_router.get("/health")
    async def health():
        SERVICE_UP.labels(service=service_name).set(1)
        return {"status": "healthy", "service": service_name}

    @health_router.get("/ready")
    async def ready():
        if check_fn:
            deps = await check_fn()
            return build_health_response(service_name, deps)
        SERVICE_UP.labels(service=service_name).set(1)
        return {"status": "ready", "service": service_name}

    return health_router
