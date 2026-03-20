"""Tests for the Model Router Gateway API."""

import pytest
from fastapi.testclient import TestClient

from services.model_router.gateway import app, cost_tracker, budget_enforcer, router


@pytest.fixture(autouse=True)
def reset_state():
    """Reset shared state between tests."""
    cost_tracker.clear()
    budget_enforcer.current_tier = None
    router.set_max_model(None)
    router._circuit_breakers.clear()
    yield


client = TestClient(app)


class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestRouteEndpoint:
    def test_route_signal_generator(self):
        resp = client.post("/route", json={"agent_type": "signal-generator"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == "google/gemini-3.0-flash"
        assert data["max_tokens"] == 2000

    def test_route_portfolio_advisor_escalation(self):
        resp = client.post(
            "/route",
            json={"agent_type": "portfolio-advisor", "opportunity_score": 90},
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "anthropic/claude-opus-4.5"

    def test_route_unknown_agent(self):
        resp = client.post("/route", json={"agent_type": "unknown"})
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "google/gemini-3.0-flash"

    def test_route_with_budget_emergency(self):
        # Simulate emergency mode by recording huge usage
        for _ in range(100):
            cost_tracker.record_usage(
                "test", "anthropic/claude-opus-4.5", 100_000, 100_000
            )
        resp = client.post("/route", json={"agent_type": "portfolio-advisor"})
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "google/gemini-3.0-flash"


class TestUsageEndpoint:
    def test_record_usage(self):
        resp = client.post(
            "/usage",
            json={
                "agent_type": "signal-generator",
                "model_id": "google/gemini-3.0-flash",
                "input_tokens": 1000,
                "output_tokens": 500,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cost_usd"] > 0
        assert data["total_tokens"] == 1500


class TestCostsEndpoint:
    def test_costs_empty(self):
        resp = client.get("/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_usd"] == 0
        assert data["total_requests"] == 0

    def test_costs_after_usage(self):
        client.post(
            "/usage",
            json={
                "agent_type": "signal-generator",
                "model_id": "google/gemini-3.0-flash",
                "input_tokens": 1000,
                "output_tokens": 500,
            },
        )
        resp = client.get("/costs")
        data = resp.json()
        assert data["total_cost_usd"] > 0
        assert data["total_requests"] == 1


class TestBudgetEndpoint:
    def test_budget_status(self):
        resp = client.get("/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly_limit_usd"] == 3000
        assert data["current_cost_usd"] == 0
        assert data["current_tier"] is None


class TestModelsEndpoint:
    def test_list_models(self):
        resp = client.get("/models")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) == 5
        # Should be sorted cheapest-first
        assert models[0]["model_id"] == "google/gemini-3.0-flash"


class TestCircuitBreakersEndpoint:
    def test_circuit_breakers_empty(self):
        resp = client.get("/circuit-breakers")
        assert resp.status_code == 200
        assert resp.json() == []
