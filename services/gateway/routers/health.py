"""Health check router."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for K8s probes."""
    return {
        "status": "healthy",
        "service": "gateway-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint for K8s probes."""
    # TODO: Add database and Redis connectivity checks
    return {
        "status": "ready",
        "service": "gateway-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
