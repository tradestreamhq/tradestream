"""
Version endpoint for all REST API services.

Reads version from the repo-root version.json at import time.
"""

import json
import os

from fastapi import APIRouter

_VERSION_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "version.json")

with open(_VERSION_FILE) as f:
    _VERSION_INFO = json.load(f)

SERVICE_VERSION: str = _VERSION_INFO["version"]
SERVICE_NAME: str = _VERSION_INFO["service"]


def create_version_router() -> APIRouter:
    """Create a router with a GET /api/v1/version endpoint."""
    version_router = APIRouter(tags=["Version"])

    @version_router.get("/api/v1/version")
    async def version():
        return {"version": SERVICE_VERSION, "service": SERVICE_NAME}

    return version_router
