"""Tests for the health check aggregator."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.janitor_agent.health_checker import (
    HealthCheckConfig,
    HealthChecker,
    ServiceHealth,
)


class TestHealthChecker:
    def _make_config(self, services=None):
        return HealthCheckConfig(
            timeout_seconds=2,
            services=services or {"test-svc": "http://localhost:9999/health"},
        )

    @patch("services.janitor_agent.health_checker.requests.get")
    def test_healthy_service(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        checker = HealthChecker(self._make_config())
        result = checker.check_service("test-svc", "http://localhost:9999/health")
        assert result.healthy is True
        assert result.status_code == 200
        assert result.service_name == "test-svc"

    @patch("services.janitor_agent.health_checker.requests.get")
    def test_unhealthy_service(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_get.return_value = mock_resp

        checker = HealthChecker(self._make_config())
        result = checker.check_service("test-svc", "http://localhost:9999/health")
        assert result.healthy is False
        assert result.status_code == 503

    @patch("services.janitor_agent.health_checker.requests.get")
    def test_timeout_service(self, mock_get):
        import requests

        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        checker = HealthChecker(self._make_config())
        result = checker.check_service("test-svc", "http://localhost:9999/health")
        assert result.healthy is False
        assert result.error == "Timeout"

    @patch("services.janitor_agent.health_checker.requests.get")
    def test_connection_error(self, mock_get):
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        checker = HealthChecker(self._make_config())
        result = checker.check_service("test-svc", "http://localhost:9999/health")
        assert result.healthy is False
        assert "Connection error" in result.error

    @patch("services.janitor_agent.health_checker.requests.get")
    def test_check_all(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        config = self._make_config(
            services={"svc1": "http://svc1/health", "svc2": "http://svc2/health"}
        )
        checker = HealthChecker(config)
        results = checker.check_all()
        assert len(results) == 2
        assert all(r.healthy for r in results)


class TestSummarize:
    def test_all_healthy(self):
        results = [
            ServiceHealth("svc1", "url", healthy=True, response_time_ms=10),
            ServiceHealth("svc2", "url", healthy=True, response_time_ms=20),
        ]
        summary = HealthChecker.summarize(results)
        assert summary["total"] == 2
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == 0
        assert summary["avg_response_ms"] == 15

    def test_some_unhealthy(self):
        results = [
            ServiceHealth("svc1", "url", healthy=True, response_time_ms=10),
            ServiceHealth(
                "svc2", "url", healthy=False, status_code=503, response_time_ms=20
            ),
        ]
        summary = HealthChecker.summarize(results)
        assert summary["unhealthy"] == 1
        assert len(summary["unhealthy_services"]) == 1
        assert summary["unhealthy_services"][0]["name"] == "svc2"

    def test_empty_results(self):
        summary = HealthChecker.summarize([])
        assert summary["total"] == 0
        assert summary["avg_response_ms"] == 0
