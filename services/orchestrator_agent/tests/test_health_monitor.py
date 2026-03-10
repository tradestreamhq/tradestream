"""Tests for health monitor and circuit breaker."""

import time
from unittest import mock

from services.orchestrator_agent import config
from services.orchestrator_agent.health_monitor import AgentHealth, HealthMonitor


class TestAgentHealth:
    def test_initial_state(self):
        h = AgentHealth("test")
        assert h.consecutive_failures == 0
        assert h.total_successes == 0
        assert h.total_failures == 0
        assert not h.is_circuit_open

    def test_record_success_resets_failures(self):
        h = AgentHealth("test")
        h.consecutive_failures = 2
        h.record_success(100)
        assert h.consecutive_failures == 0
        assert h.total_successes == 1
        assert h.last_latency_ms == 100

    def test_record_failure_increments(self):
        h = AgentHealth("test")
        h.record_failure()
        assert h.consecutive_failures == 1
        assert h.total_failures == 1

    def test_circuit_opens_after_threshold(self):
        h = AgentHealth("test")
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            h.record_failure()
        assert h.is_circuit_open

    def test_circuit_does_not_open_below_threshold(self):
        h = AgentHealth("test")
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD - 1):
            h.record_failure()
        assert not h.is_circuit_open

    @mock.patch("time.time")
    def test_circuit_closes_after_recovery(self, mock_time):
        h = AgentHealth("test")
        # Open the circuit at t=100
        mock_time.return_value = 100.0
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            h.record_failure()
        assert h.is_circuit_open

        # Still open at t=100 + recovery - 1
        mock_time.return_value = 100.0 + config.CIRCUIT_BREAKER_RECOVERY_SECONDS - 1
        assert h.is_circuit_open

        # Closed at t=100 + recovery
        mock_time.return_value = 100.0 + config.CIRCUIT_BREAKER_RECOVERY_SECONDS
        assert not h.is_circuit_open
        assert h.consecutive_failures == 0

    def test_to_dict(self):
        h = AgentHealth("test")
        h.record_success(50)
        d = h.to_dict()
        assert d["agent"] == "test"
        assert d["total_successes"] == 1
        assert d["last_latency_ms"] == 50


class TestHealthMonitor:
    def test_get_agent_health_creates_on_first_access(self):
        m = HealthMonitor()
        h = m.get_agent_health("new_agent")
        assert h.agent_name == "new_agent"

    def test_is_healthy_default(self):
        m = HealthMonitor()
        assert m.is_healthy("some_agent")

    def test_record_success(self):
        m = HealthMonitor()
        m.record_success("agent1", 200)
        h = m.get_agent_health("agent1")
        assert h.total_successes == 1

    def test_record_failure(self):
        m = HealthMonitor()
        m.record_failure("agent1")
        h = m.get_agent_health("agent1")
        assert h.total_failures == 1

    def test_circuit_breaker_integration(self):
        m = HealthMonitor()
        for _ in range(config.CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            m.record_failure("agent1")
        assert not m.is_healthy("agent1")

    def test_get_all_health(self):
        m = HealthMonitor()
        m.record_success("a", 10)
        m.record_failure("b")
        all_h = m.get_all_health()
        assert "a" in all_h
        assert "b" in all_h
