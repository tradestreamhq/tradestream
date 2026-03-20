"""Tests for the pipeline dashboard API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.autonomous_runner import dashboard
from services.autonomous_runner.dashboard import (
    DashboardState,
    SignalEventBus,
    app,
    get_event_bus,
    publish_signal_event,
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


class TestSSEStream:
    def test_signal_event_bus_publish_and_buffer(self):
        bus = SignalEventBus(buffer_size=5)
        bus.publish({"type": "signal", "data": {"symbol": "BTC-USD"}})
        bus.publish({"type": "signal", "data": {"symbol": "ETH-USD"}})
        assert bus.buffer_size == 2

    def test_signal_event_bus_subscriber_gets_replay(self):
        import asyncio

        bus = SignalEventBus(buffer_size=10)
        bus.publish({"symbol": "BTC-USD"})
        bus.publish({"symbol": "ETH-USD"})

        q = bus.subscribe()
        assert q.qsize() == 2
        assert bus.subscriber_count == 1

        bus.unsubscribe(q)
        assert bus.subscriber_count == 0

    def test_signal_event_bus_live_delivery(self):
        import asyncio

        bus = SignalEventBus()
        q = bus.subscribe()
        bus.publish({"symbol": "SOL-USD"})
        assert q.qsize() == 1

    def test_publish_signal_event(self):
        bus = get_event_bus()
        initial = bus.buffer_size
        publish_signal_event({"symbol": "BTC-USD", "action": "BUY"})
        assert bus.buffer_size == initial + 1

    def test_stream_status_endpoint(self, client):
        resp = client.get("/api/pipeline/signals/stream/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "subscribers" in data
        assert "buffer_size" in data


class TestMetricsEndpoint:
    def test_pipeline_metrics(self, client):
        resp = client.get("/api/pipeline/metrics")
        assert resp.status_code == 200
