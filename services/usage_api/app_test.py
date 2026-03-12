"""Tests for the Usage API endpoints and rate limit middleware."""

import pytest
from fastapi.testclient import TestClient

from services.usage_api.app import create_app
from services.usage_api.rate_limiter import SlidingWindowRateLimiter, TierConfig


@pytest.fixture
def limiter():
    return SlidingWindowRateLimiter(
        tier_configs={
            "free": TierConfig("free", 5),
            "basic": TierConfig("basic", 50),
            "pro": TierConfig("pro", 500),
        },
        window_seconds=3600,
    )


@pytest.fixture
def client(limiter):
    app = create_app(limiter=limiter)
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_exempt_from_rate_limit(self, client):
        # Health checks should never be rate limited
        for _ in range(10):
            resp = client.get("/health")
            assert resp.status_code == 200


class TestRateLimitHeaders:
    def test_headers_present(self, client):
        resp = client.get("/current", headers={"X-API-Key": "user1"})
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    def test_remaining_decrements(self, client):
        resp1 = client.get("/current", headers={"X-API-Key": "user1"})
        r1 = int(resp1.headers["X-RateLimit-Remaining"])

        resp2 = client.get("/current", headers={"X-API-Key": "user1"})
        r2 = int(resp2.headers["X-RateLimit-Remaining"])

        assert r2 == r1 - 1

    def test_limit_matches_tier(self, client, limiter):
        limiter.set_user_tier("pro_user", "pro")
        resp = client.get("/current", headers={"X-API-Key": "pro_user"})
        assert resp.headers["X-RateLimit-Limit"] == "500"


class TestRateLimitEnforcement:
    def test_429_when_exceeded(self, client):
        for i in range(5):
            resp = client.get("/current", headers={"X-API-Key": "limited_user"})
            assert resp.status_code == 200

        resp = client.get("/current", headers={"X-API-Key": "limited_user"})
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_429_still_has_headers(self, client):
        for _ in range(5):
            client.get("/current", headers={"X-API-Key": "limited2"})

        resp = client.get("/current", headers={"X-API-Key": "limited2"})
        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Remaining"] == "0"

    def test_different_users_independent(self, client):
        for _ in range(5):
            client.get("/current", headers={"X-API-Key": "userA"})

        # userA is blocked
        resp = client.get("/current", headers={"X-API-Key": "userA"})
        assert resp.status_code == 429

        # userB still works
        resp = client.get("/current", headers={"X-API-Key": "userB"})
        assert resp.status_code == 200


class TestCurrentUsageEndpoint:
    def test_current_usage(self, client):
        # Make a few requests first
        client.get("/current", headers={"X-API-Key": "stats_user"})
        client.get("/current", headers={"X-API-Key": "stats_user"})

        resp = client.get("/current", headers={"X-API-Key": "stats_user"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "usage"
        attrs = body["data"]["attributes"]
        assert attrs["user_id"] == "stats_user"
        assert attrs["used"] == 3
        assert attrs["tier"] == "free"

    def test_current_usage_new_user(self, client):
        resp = client.get("/current", headers={"X-API-Key": "brand_new"})
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["used"] == 1  # This request itself counts
        assert attrs["tier"] == "free"


class TestUsageHistoryEndpoint:
    def test_history(self, client):
        client.get("/current", headers={"X-API-Key": "hist_user"})
        client.get("/current", headers={"X-API-Key": "hist_user"})

        resp = client.get("/history?days=30", headers={"X-API-Key": "hist_user"})
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body

    def test_history_empty(self, client):
        resp = client.get("/history", headers={"X-API-Key": "no_history"})
        assert resp.status_code == 200
        body = resp.json()
        # At least one entry from this request itself
        assert isinstance(body["data"], list)
