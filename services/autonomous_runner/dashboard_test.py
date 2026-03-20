"""Tests for the pipeline dashboard API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.autonomous_runner import dashboard
from services.autonomous_runner.dashboard import (
    DashboardState,
    app,
    record_cycle,
    set_dashboard_state,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset dashboard state before each test."""
    dashboard._state = DashboardState()
    yield
    dashboard._state = DashboardState()


@pytest.fixture()
def client():
    return TestClient(app)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_live(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_health_ready_not_initialized(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_health_ready_when_initialized(self, client):
        mock_coord = MagicMock()
        set_dashboard_state(coordinator=mock_coord, runner_started_at=1234567890.0)
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_health_detailed_no_coordinator(self, client):
        set_dashboard_state(runner_started_at=1234567890.0)
        resp = client.get("/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert "components" in data

    def test_health_detailed_with_coordinator(self, client):
        mock_coord = MagicMock()
        mock_coord.get_pipeline_status.return_value = {
            "circuit_breaker": {"state": "closed"},
            "adaptive": {"batch_size": 10},
            "db_persistence": True,
        }
        mock_coord.risk_manager.get_status.return_value = {"active_signals": 0}
        set_dashboard_state(coordinator=mock_coord, runner_started_at=1234567890.0)

        resp = client.get("/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["components"]["coordinator"]["status"] == "up"


class TestPipelineEndpoints:
    def test_pipeline_status_no_coordinator(self, client):
        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False

    def test_pipeline_status_with_coordinator(self, client):
        mock_coord = MagicMock()
        mock_coord.get_pipeline_status.return_value = {"instance_id": "test"}
        mock_ks = MagicMock()
        mock_ks.get_status.return_value = {"active": False}
        set_dashboard_state(
            coordinator=mock_coord,
            kill_switch=mock_ks,
            runner_started_at=1234567890.0,
        )
        record_cycle(150, 3)

        resp = client.get("/api/pipeline/status")
        data = resp.json()
        assert data["running"] is True
        assert data["total_cycles"] == 1
        assert data["total_signals_emitted"] == 3

    def test_recent_decisions_empty(self, client):
        resp = client.get("/api/pipeline/decisions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_recent_decisions_with_data(self, client):
        mock_coord = MagicMock()
        mock_coord.get_recent_decisions.return_value = [
            {"symbol": "BTC-USD", "action": "BUY"},
            {"symbol": "ETH-USD", "action": "SELL"},
        ]
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/decisions?limit=10")
        data = resp.json()
        assert data["total"] == 2

    def test_recent_decisions_filtered_by_symbol(self, client):
        mock_coord = MagicMock()
        mock_coord.get_recent_decisions.return_value = [
            {"symbol": "BTC-USD", "action": "BUY"},
            {"symbol": "ETH-USD", "action": "SELL"},
        ]
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/decisions?symbol=BTC-USD")
        data = resp.json()
        assert data["total"] == 1
        assert data["decisions"][0]["symbol"] == "BTC-USD"

    def test_risk_status_no_coordinator(self, client):
        resp = client.get("/api/pipeline/risk")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_risk_status_with_coordinator(self, client):
        mock_coord = MagicMock()
        mock_coord.risk_manager.get_status.return_value = {
            "active_signals": 2,
            "portfolio_exposure": 0.15,
        }
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/risk")
        data = resp.json()
        assert data["active_signals"] == 2


class TestKillSwitchEndpoints:
    def test_kill_switch_status_not_initialized(self, client):
        resp = client.get("/api/pipeline/kill-switch")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_activate_kill_switch(self, client):
        mock_ks = MagicMock()
        mock_ks.activate.return_value = True
        mock_ks.get_status.return_value = {"active": True, "reason": "test"}
        set_dashboard_state(kill_switch=mock_ks)

        resp = client.post(
            "/api/pipeline/kill-switch/activate",
            json={"reason": "test", "activated_by": "unit-test"},
        )
        data = resp.json()
        assert data["success"] is True
        mock_ks.activate.assert_called_once()

    def test_deactivate_kill_switch(self, client):
        mock_ks = MagicMock()
        mock_ks.deactivate.return_value = True
        mock_ks.get_status.return_value = {"active": False}
        set_dashboard_state(kill_switch=mock_ks)

        resp = client.post("/api/pipeline/kill-switch/deactivate")
        data = resp.json()
        assert data["success"] is True

    def test_activate_kill_switch_not_initialized(self, client):
        resp = client.post(
            "/api/pipeline/kill-switch/activate",
            json={"reason": "test"},
        )
        assert "error" in resp.json()


class TestAnalyticsEndpoints:
    def test_decision_analytics_no_coordinator(self, client):
        resp = client.get("/api/pipeline/analytics/decisions")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_decision_analytics_empty(self, client):
        mock_coord = MagicMock()
        mock_coord.get_recent_decisions.return_value = []
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/analytics/decisions")
        data = resp.json()
        assert data["total"] == 0

    def test_decision_analytics_with_data(self, client):
        mock_coord = MagicMock()
        mock_coord.get_recent_decisions.return_value = [
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.85,
                "risk_approved": True,
                "opportunity_score": 82,
                "risk_rejection_reasons": [],
            },
            {
                "symbol": "ETH-USD",
                "action": "SELL",
                "confidence": 0.70,
                "risk_approved": False,
                "opportunity_score": 35,
                "risk_rejection_reasons": ["max_concurrent"],
            },
            {
                "symbol": "SOL-USD",
                "action": "HOLD",
                "confidence": 0.40,
                "risk_approved": True,
                "opportunity_score": 55,
                "risk_rejection_reasons": [],
            },
        ]
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/analytics/decisions")
        data = resp.json()
        assert data["total"] == 3
        assert data["action_distribution"]["BUY"] == 1
        assert data["action_distribution"]["SELL"] == 1
        assert data["action_distribution"]["HOLD"] == 1
        assert data["confidence_stats"]["max"] == 0.85
        assert data["opportunity_tiers"]["HOT"] == 1
        assert data["opportunity_tiers"]["LOW"] == 1
        assert data["risk_rejections"]["total_rejected"] == 1

    def test_signal_analytics_no_coordinator(self, client):
        resp = client.get("/api/pipeline/analytics/signals")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_signal_analytics_by_symbol(self, client):
        mock_coord = MagicMock()
        mock_coord.get_recent_decisions.return_value = [
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.80,
                "fusion_agreement_ratio": 0.75,
                "risk_approved": True,
            },
            {
                "symbol": "BTC-USD",
                "action": "BUY",
                "confidence": 0.90,
                "fusion_agreement_ratio": 0.85,
                "risk_approved": True,
            },
        ]
        set_dashboard_state(coordinator=mock_coord)

        resp = client.get("/api/pipeline/analytics/signals?symbol=BTC-USD")
        data = resp.json()
        assert data["total_symbols"] == 1
        btc = data["symbols"]["BTC-USD"]
        assert btc["count"] == 2
        assert btc["approved"] == 2
        assert btc["avg_confidence"] == 0.85

    def test_event_bus_status(self, client):
        resp = client.get("/api/pipeline/event-bus")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data
        assert "subscriber_count" in data


class TestSSEStream:
    def test_sse_stream_returns_event_stream(self, client):
        """Test that the SSE endpoint returns correct content type."""
        # Use stream=True for SSE and close quickly
        with client.stream("GET", "/api/pipeline/stream") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # Don't consume the body — just validate headers
            resp.close()


class TestMetricsEndpoint:
    def test_pipeline_metrics(self, client):
        resp = client.get("/api/pipeline/metrics")
        assert resp.status_code == 200
