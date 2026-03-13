"""Tests for the Health Monitoring REST API."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.health_monitoring_api.app import (
    _compute_percentiles,
    create_app,
    record_request_latency,
)


def _make_pool():
    """Create a mock asyncpg pool with async context manager support."""
    pool = AsyncMock()
    conn = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


@pytest.fixture
def full_client():
    """Client with Redis and exchange mocks."""
    pool, conn = _make_pool()
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    exchange = AsyncMock()
    exchange.fetch_status = AsyncMock(return_value={"status": "ok"})
    app = create_app(pool, redis_client=redis, exchange_client=exchange)
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn, redis, exchange


class TestBasicHealth:
    def test_health_returns_200(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "health-monitoring-api"


class TestDetailedHealth:
    def test_detailed_healthy(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health/detailed")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "healthy"
        assert "dependencies" in attrs
        assert "uptime_seconds" in attrs

    def test_detailed_degraded_db(self, client):
        tc, conn = client
        conn.fetchval.side_effect = Exception("connection refused")
        resp = tc.get("/health/detailed")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "degraded"
        assert "connection refused" in attrs["dependencies"]["postgres"]

    def test_detailed_with_all_deps_ok(self, full_client):
        tc, conn, redis, exchange = full_client
        conn.fetchval.return_value = 1
        resp = tc.get("/health/detailed")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "healthy"
        assert attrs["dependencies"]["postgres"] == "ok"
        assert attrs["dependencies"]["redis"] == "ok"
        assert attrs["dependencies"]["exchange"] == "ok"

    def test_detailed_redis_down(self, full_client):
        tc, conn, redis, exchange = full_client
        conn.fetchval.return_value = 1
        redis.ping.side_effect = Exception("redis timeout")
        resp = tc.get("/health/detailed")
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "degraded"
        assert "redis timeout" in attrs["dependencies"]["redis"]


class TestSystemMetrics:
    def test_metrics_success(self, client):
        tc, conn = client
        # fetchval called 3 times: active_strategies, open_positions, signals_per_hour
        conn.fetchval.side_effect = [10, 5, 42]
        resp = tc.get("/system/metrics")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["active_strategies"] == 10
        assert attrs["open_positions"] == 5
        assert attrs["signals_per_hour"] == 42
        assert "api_latency_ms" in attrs
        assert "p50" in attrs["api_latency_ms"]
        assert "p90" in attrs["api_latency_ms"]
        assert "p99" in attrs["api_latency_ms"]
        assert "total_requests" in attrs
        assert "uptime_seconds" in attrs

    def test_metrics_db_error(self, client):
        tc, conn = client
        conn.fetchval.side_effect = Exception("db down")
        resp = tc.get("/system/metrics")
        assert resp.status_code == 500


class TestSystemStatus:
    def test_status_operational(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/system/status")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "operational"
        assert "database" in attrs["components"]
        assert "redis" in attrs["components"]
        assert "exchange_connector" in attrs["components"]
        assert "websocket" in attrs["components"]

    def test_status_degraded_db(self, client):
        tc, conn = client
        conn.fetchval.side_effect = Exception("connection refused")
        resp = tc.get("/system/status")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "degraded"

    def test_status_all_deps(self, full_client):
        tc, conn, redis, exchange = full_client
        conn.fetchval.return_value = 1
        resp = tc.get("/system/status")
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "operational"
        assert attrs["components"]["database"]["status"] == "ok"
        assert attrs["components"]["redis"]["status"] == "ok"
        assert attrs["components"]["exchange_connector"]["status"] == "ok"
        assert attrs["components"]["websocket"]["status"] == "ok"


class TestPrometheusMetrics:
    def test_metrics_format(self, client):
        tc, conn = client
        conn.fetchval.side_effect = [1, 3, 2, 7]  # health check + 3 DB queries
        resp = tc.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        text = resp.text
        assert "tradestream_uptime_seconds" in text
        assert "tradestream_http_requests_total" in text
        assert "tradestream_http_request_duration_ms" in text
        assert "tradestream_dependency_up" in text
        assert "tradestream_active_strategies" in text
        assert "tradestream_open_positions" in text
        assert "tradestream_signals_per_hour" in text

    def test_metrics_has_help_and_type(self, client):
        tc, conn = client
        conn.fetchval.side_effect = [1, 3, 2, 7]
        resp = tc.get("/metrics")
        text = resp.text
        assert "# HELP tradestream_uptime_seconds" in text
        assert "# TYPE tradestream_uptime_seconds gauge" in text
        assert "# TYPE tradestream_http_requests_total counter" in text

    def test_metrics_db_failure_still_returns(self, client):
        tc, conn = client
        conn.fetchval.side_effect = Exception("db down")
        resp = tc.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        # Should still have uptime and request count even if DB fails
        assert "tradestream_uptime_seconds" in text
        assert "tradestream_http_requests_total" in text


class TestPercentileComputation:
    def test_empty_list(self):
        result = _compute_percentiles([])
        assert result == {"p50": 0.0, "p90": 0.0, "p99": 0.0}

    def test_single_value(self):
        result = _compute_percentiles([5.0])
        assert result["p50"] == 5.0

    def test_known_distribution(self):
        values = list(range(1, 101))  # 1..100
        result = _compute_percentiles(values)
        assert result["p50"] == 50.0
        assert result["p90"] == 90.0
        assert result["p99"] == 99.0


class TestRecordLatency:
    def test_records_latency(self):
        from services.health_monitoring_api import app as app_module

        original = app_module._metrics["api_latencies"][:]
        original_count = app_module._metrics["request_count"]
        record_request_latency(12.5)
        assert app_module._metrics["request_count"] == original_count + 1
        assert 12.5 in app_module._metrics["api_latencies"]
