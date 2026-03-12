"""Shared monitoring infrastructure for all TradeStream services.

Provides Prometheus metrics, health check utilities, and HTTP middleware
for both FastAPI and Flask services. Worker services without their own
HTTP server can use ``start_metrics_server`` to expose /health and /metrics
on a dedicated port.
"""

import asyncio
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard metric definitions (shared singleton registry)
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

MESSAGES_PROCESSED = Counter(
    "messages_processed_total",
    "Total messages consumed from queues",
    ["service", "topic"],
)

MESSAGE_PROCESSING_LATENCY = Histogram(
    "message_processing_duration_seconds",
    "Message processing latency in seconds",
    ["service", "topic"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Current queue depth / lag",
    ["service", "topic"],
)

SIGNALS_GENERATED = Counter(
    "signals_generated_total",
    "Total trading signals generated",
    ["service", "signal_type"],
)

TRADES_EXECUTED = Counter(
    "trades_executed_total",
    "Total trades executed (paper or live)",
    ["service", "side", "mode"],
)

SERVICE_UP = Gauge(
    "service_up",
    "Whether the service is healthy (1) or unhealthy (0)",
    ["service"],
)

DEPENDENCY_UP = Gauge(
    "dependency_up",
    "Whether a dependency is reachable (1) or not (0)",
    ["service", "dependency"],
)


# ---------------------------------------------------------------------------
# Health check utilities
# ---------------------------------------------------------------------------


async def check_postgres(pool) -> str:
    """Check PostgreSQL connectivity via an asyncpg pool."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "ok"
    except Exception as e:
        return str(e)


async def check_redis(client) -> str:
    """Check Redis connectivity via a redis client."""
    try:
        await client.ping()
        return "ok"
    except Exception:
        pass
    # Synchronous redis client fallback
    try:
        client.ping()
        return "ok"
    except Exception as e:
        return str(e)


def check_kafka_sync(consumer) -> str:
    """Check Kafka connectivity via a kafka-python consumer."""
    try:
        topics = consumer.topics()
        if topics is not None:
            return "ok"
        return "no topics returned"
    except Exception as e:
        return str(e)


async def check_http_endpoint(url: str, timeout: float = 5.0) -> str:
    """Check reachability of an HTTP endpoint."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code < 500:
                return "ok"
            return f"status={resp.status_code}"
    except Exception as e:
        return str(e)


def build_health_response(
    service_name: str, dependencies: Dict[str, str]
) -> Dict[str, Any]:
    """Build a standardised health response dict and update Prometheus gauges."""
    all_ok = all(v == "ok" for v in dependencies.values())
    status = "healthy" if all_ok else "degraded"

    SERVICE_UP.labels(service=service_name).set(1 if all_ok else 0)
    for dep_name, dep_status in dependencies.items():
        DEPENDENCY_UP.labels(service=service_name, dependency=dep_name).set(
            1 if dep_status == "ok" else 0
        )

    return {
        "status": status,
        "service": service_name,
        "dependencies": dependencies,
    }


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


def add_fastapi_metrics(app, service_name: str):
    """Add Prometheus request metrics middleware to a FastAPI app.

    Also mounts a ``/metrics`` endpoint that serves the Prometheus
    text exposition format.
    """
    from fastapi import Request, Response
    from fastapi.responses import PlainTextResponse

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        path = request.url.path
        # Skip metrics endpoint itself to avoid recursion in dashboards
        if path == "/metrics":
            return response

        REQUEST_COUNT.labels(
            service=service_name,
            method=request.method,
            endpoint=path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            service=service_name,
            method=request.method,
            endpoint=path,
        ).observe(elapsed)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return PlainTextResponse(
            generate_latest(REGISTRY),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


# ---------------------------------------------------------------------------
# Flask middleware
# ---------------------------------------------------------------------------


def add_flask_metrics(app, service_name: str):
    """Add Prometheus request metrics middleware to a Flask app.

    Also registers a ``/metrics`` endpoint.
    """
    from flask import request as flask_request, Response as FlaskResponse

    @app.before_request
    def _start_timer():
        flask_request._prom_start = time.monotonic()

    @app.after_request
    def _record_metrics(response):
        start = getattr(flask_request, "_prom_start", None)
        if start is None:
            return response

        elapsed = time.monotonic() - start
        path = flask_request.path

        if path == "/metrics":
            return response

        REQUEST_COUNT.labels(
            service=service_name,
            method=flask_request.method,
            endpoint=path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            service=service_name,
            method=flask_request.method,
            endpoint=path,
        ).observe(elapsed)
        return response

    @app.route("/metrics")
    def metrics():
        return FlaskResponse(
            generate_latest(REGISTRY),
            mimetype="text/plain; version=0.0.4; charset=utf-8",
        )


# ---------------------------------------------------------------------------
# Standalone metrics server for worker / consumer services
# ---------------------------------------------------------------------------


class _MetricsHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP handler exposing /health and /metrics."""

    # Set by start_metrics_server via a factory closure
    service_name: str = "unknown"
    health_fn: Optional[Callable] = None

    def do_GET(self):
        if self.path == "/health":
            self._serve_health()
        elif self.path == "/metrics":
            self._serve_metrics()
        else:
            self.send_error(404)

    def _serve_health(self):
        import json

        deps: Dict[str, str] = {}
        if self.health_fn is not None:
            try:
                result = self.health_fn()
                # Support both sync dicts and awaitable coroutines
                if asyncio.iscoroutine(result):
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(result)
                    finally:
                        loop.close()
                deps = result
            except Exception as e:
                deps = {"check": str(e)}

        body = build_health_response(self.service_name, deps)
        status_code = 200 if body["status"] == "healthy" else 503
        payload = json.dumps(body).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_metrics(self):
        payload = generate_latest(REGISTRY)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        # Suppress default stderr logging
        pass


def start_metrics_server(
    service_name: str,
    port: int = 9090,
    health_fn: Optional[Callable] = None,
) -> HTTPServer:
    """Start a background HTTP server exposing /health and /metrics.

    Intended for worker/consumer services that don't have their own HTTP
    server.  The server runs in a daemon thread and will not prevent
    process exit.

    Args:
        service_name: Identifier for this service in metric labels.
        port: TCP port to bind.
        health_fn: Optional callable returning ``Dict[str, str]`` of
            dependency statuses.  May be sync or async.

    Returns:
        The ``HTTPServer`` instance (already serving in a background thread).
    """

    # Create a handler subclass so each server gets its own config
    class Handler(_MetricsHandler):
        pass

    Handler.service_name = service_name
    Handler.health_fn = health_fn

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name=f"{service_name}-metrics",
    )
    thread.start()
    logger.info("Metrics server for %s listening on :%d", service_name, port)

    SERVICE_UP.labels(service=service_name).set(1)

    return server
