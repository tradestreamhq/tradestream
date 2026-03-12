"""Tests for the health check router."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from services.rest_api_shared.health import create_health_router


@pytest.mark.asyncio
async def test_health_returns_healthy():
    app = FastAPI()
    app.include_router(create_health_router("test-svc"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "test-svc"


@pytest.mark.asyncio
async def test_ready_without_check_fn():
    app = FastAPI()
    app.include_router(create_health_router("test-svc"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_healthy_deps():
    async def check():
        return {"postgres": "ok"}

    app = FastAPI()
    app.include_router(create_health_router("test-svc", check_fn=check))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["dependencies"]["postgres"] == "ok"


@pytest.mark.asyncio
async def test_ready_degraded_deps():
    async def check():
        return {"postgres": "ok", "redis": "connection refused"}

    app = FastAPI()
    app.include_router(create_health_router("test-svc", check_fn=check))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
