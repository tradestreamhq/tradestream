"""Tests for the version endpoint."""

from unittest.mock import mock_open, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.rest_api_shared.version import (
    SERVICE_NAME,
    SERVICE_VERSION,
    create_version_router,
)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_version_router())
    return TestClient(app)


class TestVersionEndpoint:
    def test_returns_version_and_service(self, client):
        resp = client.get("/api/v1/version")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == SERVICE_VERSION
        assert body["service"] == SERVICE_NAME

    def test_version_is_semver(self, client):
        resp = client.get("/api/v1/version")
        version = resp.json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_service_name_is_tradestream(self, client):
        resp = client.get("/api/v1/version")
        assert resp.json()["service"] == "tradestream"
