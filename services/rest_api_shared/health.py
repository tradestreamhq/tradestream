"""
Standard health check endpoints for all REST API services.
"""

from fastapi import APIRouter

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
        return {"status": "healthy", "service": service_name}

    @health_router.get("/ready")
    async def ready():
        result = {"status": "ready", "service": service_name}
        if check_fn:
            deps = await check_fn()
            result["dependencies"] = deps
            if any(v != "ok" for v in deps.values()):
                result["status"] = "degraded"
                return result
        return result

    return health_router
