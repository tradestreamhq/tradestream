"""Health monitoring with circuit breaker for agent services."""

import time
from collections import defaultdict

from absl import logging

from services.orchestrator_agent import config


class AgentHealth:
    """Tracks health metrics for a single agent."""

    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.consecutive_failures = 0
        self.total_successes = 0
        self.total_failures = 0
        self.circuit_open_until = 0.0
        self.last_latency_ms = 0

    @property
    def is_circuit_open(self):
        """Check if the circuit breaker is currently open (agent paused)."""
        if self.circuit_open_until == 0.0:
            return False
        if time.time() >= self.circuit_open_until:
            # Recovery period elapsed, close the circuit
            logging.info(
                "%s: circuit breaker recovery period elapsed, closing circuit",
                self.agent_name,
            )
            self.circuit_open_until = 0.0
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self, latency_ms):
        """Record a successful agent execution."""
        self.consecutive_failures = 0
        self.total_successes += 1
        self.last_latency_ms = latency_ms

    def record_failure(self):
        """Record a failed agent execution. Opens circuit breaker if threshold reached."""
        self.consecutive_failures += 1
        self.total_failures += 1

        if self.consecutive_failures >= config.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            self.circuit_open_until = (
                time.time() + config.CIRCUIT_BREAKER_RECOVERY_SECONDS
            )
            logging.warning(
                "%s: circuit breaker OPEN after %d consecutive failures. "
                "Pausing for %ds.",
                self.agent_name,
                self.consecutive_failures,
                config.CIRCUIT_BREAKER_RECOVERY_SECONDS,
            )

    def to_dict(self):
        """Return health metrics as a dict."""
        return {
            "agent": self.agent_name,
            "consecutive_failures": self.consecutive_failures,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "circuit_open": self.is_circuit_open,
            "last_latency_ms": self.last_latency_ms,
        }


class HealthMonitor:
    """Monitors health of all agent services."""

    def __init__(self):
        self._agents = {}

    def get_agent_health(self, agent_name):
        """Get or create health tracker for an agent."""
        if agent_name not in self._agents:
            self._agents[agent_name] = AgentHealth(agent_name)
        return self._agents[agent_name]

    def is_healthy(self, agent_name):
        """Check if an agent is healthy (circuit breaker closed)."""
        health = self.get_agent_health(agent_name)
        return not health.is_circuit_open

    def record_success(self, agent_name, latency_ms):
        """Record a successful agent execution."""
        health = self.get_agent_health(agent_name)
        health.record_success(latency_ms)
        logging.info(
            "%s: success (latency=%dms, total_success=%d)",
            agent_name,
            latency_ms,
            health.total_successes,
        )

    def record_failure(self, agent_name):
        """Record a failed agent execution."""
        health = self.get_agent_health(agent_name)
        health.record_failure()
        logging.warning(
            "%s: failure (consecutive=%d, total_failures=%d)",
            agent_name,
            health.consecutive_failures,
            health.total_failures,
        )

    def get_all_health(self):
        """Return health metrics for all tracked agents."""
        return {name: h.to_dict() for name, h in self._agents.items()}
