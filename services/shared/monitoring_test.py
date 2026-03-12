"""Tests for the shared monitoring module."""

import asyncio
import json
import threading
import time
import urllib.request
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY, CollectorRegistry

from services.shared.monitoring import (
    DEPENDENCY_UP,
    MESSAGES_PROCESSED,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    SERVICE_UP,
    SIGNALS_GENERATED,
    TRADES_EXECUTED,
    add_fastapi_metrics,
    add_flask_metrics,
    build_health_response,
    check_http_endpoint,
    check_kafka_sync,
    check_postgres,
    check_redis,
    start_metrics_server,
)


# ---------------------------------------------------------------------------
# Health check utilities
# ---------------------------------------------------------------------------


class TestCheckPostgres:
    @pytest.mark.asyncio
    async def test_healthy_pool(self):
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=1)
        pool = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await check_postgres(pool)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unhealthy_pool(self):
        pool = AsyncMock()
        pool.acquire.side_effect = ConnectionRefusedError("connection refused")
        result = await check_postgres(pool)
        assert "connection refused" in result


class TestCheckRedis:
    @pytest.mark.asyncio
    async def test_async_redis_healthy(self):
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        result = await check_redis(client)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_sync_redis_healthy(self):
        """Falls back to sync ping when async ping raises."""
        client = MagicMock()
        # First call (async) raises, second call (sync) succeeds
        client.ping = MagicMock(side_effect=[TypeError("not awaitable"), True])
        # Override with a non-async version for the first attempt
        async_mock = AsyncMock(side_effect=Exception("async fail"))
        client.ping = MagicMock(return_value=True)
        result = await check_redis(client)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_redis_unhealthy(self):
        client = MagicMock()
        client.ping = MagicMock(side_effect=ConnectionError("redis down"))
        result = await check_redis(client)
        assert "redis down" in result


class TestCheckKafkaSync:
    def test_healthy_consumer(self):
        consumer = MagicMock()
        consumer.topics.return_value = {"topic-a", "topic-b"}
        assert check_kafka_sync(consumer) == "ok"

    def test_unhealthy_consumer(self):
        consumer = MagicMock()
        consumer.topics.side_effect = Exception("broker unavailable")
        result = check_kafka_sync(consumer)
        assert "broker unavailable" in result

    def test_no_topics(self):
        consumer = MagicMock()
        consumer.topics.return_value = None
        result = check_kafka_sync(consumer)
        assert result == "no topics returned"


class TestCheckHttpEndpoint:
    @pytest.mark.asyncio
    async def test_reachable(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check_http_endpoint("http://example.com/health")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unreachable(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await check_http_endpoint("http://down.local/health")
        assert "refused" in result


# ---------------------------------------------------------------------------
# build_health_response
# ---------------------------------------------------------------------------


class TestBuildHealthResponse:
    def test_all_healthy(self):
        resp = build_health_response("test-svc", {"postgres": "ok", "redis": "ok"})
        assert resp["status"] == "healthy"
        assert resp["service"] == "test-svc"
        assert resp["dependencies"]["postgres"] == "ok"

    def test_degraded(self):
        resp = build_health_response(
            "test-svc", {"postgres": "ok", "redis": "connection refused"}
        )
        assert resp["status"] == "degraded"

    def test_updates_prometheus_gauges(self):
        build_health_response("gauge-test", {"db": "ok", "cache": "error"})
        # Verify gauges were set (no exception = success)
        assert SERVICE_UP.labels(service="gauge-test")._value.get() == 0
        assert DEPENDENCY_UP.labels(service="gauge-test", dependency="db")._value.get() == 1
        assert DEPENDENCY_UP.labels(service="gauge-test", dependency="cache")._value.get() == 0


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class TestFastAPIMetrics:
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        add_fastapi_metrics(app, "test-fastapi")

        @app.get("/hello")
        async def hello():
            return {"msg": "world"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Hit a normal endpoint to generate metrics
            resp = await client.get("/hello")
            assert resp.status_code == 200

            # Check /metrics endpoint
            resp = await client.get("/metrics")
            assert resp.status_code == 200
            body = resp.text
            assert "http_requests_total" in body
            assert "http_request_duration_seconds" in body

    @pytest.mark.asyncio
    async def test_request_counted(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        add_fastapi_metrics(app, "count-test")

        @app.get("/ping")
        async def ping():
            return "pong"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/ping")
            await client.get("/ping")

            resp = await client.get("/metrics")
            body = resp.text
            # Should see count-test service label
            assert "count-test" in body


# ---------------------------------------------------------------------------
# Flask middleware
# ---------------------------------------------------------------------------


class TestFlaskMetrics:
    def test_metrics_endpoint(self):
        from flask import Flask

        app = Flask(__name__)
        add_flask_metrics(app, "test-flask")

        @app.route("/hello")
        def hello():
            return "world"

        with app.test_client() as client:
            resp = client.get("/hello")
            assert resp.status_code == 200

            resp = client.get("/metrics")
            assert resp.status_code == 200
            body = resp.data.decode()
            assert "http_requests_total" in body

    def test_request_counted(self):
        from flask import Flask

        app = Flask(__name__)
        add_flask_metrics(app, "flask-count")

        @app.route("/ping")
        def ping():
            return "pong"

        with app.test_client() as client:
            client.get("/ping")
            client.get("/ping")

            resp = client.get("/metrics")
            body = resp.data.decode()
            assert "flask-count" in body


# ---------------------------------------------------------------------------
# Standalone metrics server
# ---------------------------------------------------------------------------


class TestMetricsServer:
    def test_health_endpoint(self):
        server = start_metrics_server("worker-test", port=0)
        port = server.server_address[1]
        try:
            resp = urllib.request.urlopen(f"http://localhost:{port}/health")
            data = json.loads(resp.read())
            assert data["status"] == "healthy"
            assert data["service"] == "worker-test"
        finally:
            server.shutdown()

    def test_metrics_endpoint(self):
        server = start_metrics_server("worker-metrics", port=0)
        port = server.server_address[1]
        try:
            resp = urllib.request.urlopen(f"http://localhost:{port}/metrics")
            body = resp.read().decode()
            assert "service_up" in body
        finally:
            server.shutdown()

    def test_health_with_check_fn(self):
        def check():
            return {"database": "ok", "kafka": "ok"}

        server = start_metrics_server("worker-deps", port=0, health_fn=check)
        port = server.server_address[1]
        try:
            resp = urllib.request.urlopen(f"http://localhost:{port}/health")
            data = json.loads(resp.read())
            assert data["status"] == "healthy"
            assert data["dependencies"]["database"] == "ok"
        finally:
            server.shutdown()

    def test_health_degraded(self):
        def check():
            return {"database": "ok", "kafka": "broker down"}

        server = start_metrics_server("worker-degraded", port=0, health_fn=check)
        port = server.server_address[1]
        try:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"http://localhost:{port}/health")
            assert exc_info.value.code == 503
        finally:
            server.shutdown()

    def test_404_for_unknown_path(self):
        server = start_metrics_server("worker-404", port=0)
        port = server.server_address[1]
        try:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"http://localhost:{port}/unknown")
            assert exc_info.value.code == 404
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# Metric helpers (counters, gauges, etc.)
# ---------------------------------------------------------------------------


class TestMetricDefinitions:
    def test_request_count_labels(self):
        REQUEST_COUNT.labels(
            service="test", method="GET", endpoint="/test", status=200
        ).inc()

    def test_request_latency_labels(self):
        REQUEST_LATENCY.labels(
            service="test", method="GET", endpoint="/test"
        ).observe(0.1)

    def test_messages_processed_labels(self):
        MESSAGES_PROCESSED.labels(service="test", topic="test-topic").inc()

    def test_signals_generated_labels(self):
        SIGNALS_GENERATED.labels(service="test", signal_type="BUY").inc()

    def test_trades_executed_labels(self):
        TRADES_EXECUTED.labels(service="test", side="BUY", mode="paper").inc()
