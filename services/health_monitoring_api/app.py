"""
Health Check and System Monitoring REST API.

Provides endpoints for health checks, system metrics, component status,
and Prometheus-compatible metrics export.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, FastAPI
from fastapi.responses import PlainTextResponse

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    error_response,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

# In-memory metrics counters
_metrics: Dict[str, Any] = {
    "request_count": 0,
    "api_latencies": [],  # Recent latency samples in ms
    "start_time": time.time(),
}

MAX_LATENCY_SAMPLES = 1000


def record_request_latency(latency_ms: float) -> None:
    """Record an API request latency sample."""
    _metrics["request_count"] += 1
    samples = _metrics["api_latencies"]
    samples.append(latency_ms)
    if len(samples) > MAX_LATENCY_SAMPLES:
        _metrics["api_latencies"] = samples[-MAX_LATENCY_SAMPLES:]


def _compute_percentiles(values: List[float]) -> Dict[str, float]:
    """Compute p50, p90, p99 percentiles from a list of values."""
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def percentile(p: float) -> float:
        idx = int(p / 100.0 * (n - 1))
        return round(sorted_vals[idx], 2)

    return {
        "p50": percentile(50),
        "p90": percentile(90),
        "p99": percentile(99),
    }


async def _check_postgres(db_pool: asyncpg.Pool) -> str:
    """Check PostgreSQL connectivity."""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return "ok"
    except Exception as e:
        logger.warning("Postgres health check failed: %s", e)
        return str(e)


async def _check_redis(redis_client: Any) -> str:
    """Check Redis connectivity."""
    if redis_client is None:
        return "not_configured"
    try:
        await redis_client.ping()
        return "ok"
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return str(e)


async def _check_exchange(exchange_client: Any) -> str:
    """Check exchange connector connectivity."""
    if exchange_client is None:
        return "not_configured"
    try:
        await exchange_client.fetch_status()
        return "ok"
    except Exception as e:
        logger.warning("Exchange health check failed: %s", e)
        return str(e)


def create_app(
    db_pool: asyncpg.Pool,
    redis_client: Any = None,
    exchange_client: Any = None,
) -> FastAPI:
    """Create the Health Monitoring API FastAPI application."""
    app = FastAPI(
        title="Health Monitoring API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1",
    )
    fastapi_auth_middleware(app)

    _metrics["start_time"] = time.time()

    # --- Middleware to track latency ---

    @app.middleware("http")
    async def track_latency(request, call_next):
        start = time.time()
        response = await call_next(request)
        latency_ms = (time.time() - start) * 1000
        record_request_latency(latency_ms)
        return response

    # --- Basic health ---

    async def check_deps():
        results = {}
        results["postgres"] = await _check_postgres(db_pool)
        results["redis"] = await _check_redis(redis_client)
        results["exchange"] = await _check_exchange(exchange_client)
        return results

    app.include_router(
        create_health_router("health-monitoring-api", check_deps),
        prefix="/health",
        tags=["Health"],
    )

    # --- GET /health --- (basic)

    @app.get("/health", tags=["Health"])
    async def basic_health():
        """Basic health check — returns 200 if the service is running."""
        return {"status": "healthy", "service": "health-monitoring-api"}

    # --- GET /health/detailed --- (detailed with dependency checks)

    @app.get("/health/detailed", tags=["Health"])
    async def detailed_health():
        """Detailed health check with DB, Redis, and exchange status."""
        deps = await check_deps()
        overall = "healthy" if all(v == "ok" or v == "not_configured" for v in deps.values()) else "degraded"
        return success_response(
            {
                "status": overall,
                "service": "health-monitoring-api",
                "uptime_seconds": round(time.time() - _metrics["start_time"], 1),
                "dependencies": deps,
            },
            "health_detail",
        )

    # --- GET /system/metrics ---

    @app.get("/system/metrics", tags=["System"])
    async def system_metrics():
        """System metrics: active strategies, open positions, signals/hour, API latency."""
        try:
            async with db_pool.acquire() as conn:
                active_strategies = await conn.fetchval(
                    "SELECT COUNT(*) FROM strategy_specs WHERE source != 'DISABLED'"
                ) or 0

                open_positions = await conn.fetchval(
                    "SELECT COUNT(*) FROM paper_portfolio WHERE quantity != 0"
                ) or 0

                signals_per_hour = await conn.fetchval(
                    "SELECT COUNT(*) FROM signals "
                    "WHERE created_at > NOW() - INTERVAL '1 hour'"
                ) or 0
        except Exception as e:
            logger.error("Failed to query system metrics: %s", e)
            return server_error("Failed to retrieve system metrics")

        latency_percentiles = _compute_percentiles(_metrics["api_latencies"])

        return success_response(
            {
                "active_strategies": active_strategies,
                "open_positions": open_positions,
                "signals_per_hour": signals_per_hour,
                "api_latency_ms": latency_percentiles,
                "total_requests": _metrics["request_count"],
                "uptime_seconds": round(time.time() - _metrics["start_time"], 1),
            },
            "system_metrics",
        )

    # --- GET /system/status ---

    @app.get("/system/status", tags=["System"])
    async def system_status():
        """Component status: exchange connectors, WebSocket, database."""
        components = {}

        # Database
        components["database"] = {
            "status": await _check_postgres(db_pool),
            "type": "postgresql",
        }

        # Redis
        redis_status = await _check_redis(redis_client)
        components["redis"] = {
            "status": redis_status,
            "type": "redis",
        }

        # Exchange connector
        exchange_status = await _check_exchange(exchange_client)
        components["exchange_connector"] = {
            "status": exchange_status,
            "type": "ccxt",
        }

        # WebSocket (derived from exchange status)
        components["websocket"] = {
            "status": exchange_status if exchange_status in ("ok", "not_configured") else "degraded",
            "type": "websocket",
        }

        overall = "operational"
        statuses = [c["status"] for c in components.values()]
        if any(s not in ("ok", "not_configured") for s in statuses):
            overall = "degraded"

        return success_response(
            {
                "status": overall,
                "components": components,
            },
            "system_status",
        )

    # --- GET /metrics (Prometheus-compatible) ---

    @app.get("/metrics", tags=["Metrics"], response_class=PlainTextResponse)
    async def prometheus_metrics():
        """Prometheus-compatible metrics endpoint."""
        lines = []

        # Uptime
        uptime = round(time.time() - _metrics["start_time"], 1)
        lines.append("# HELP tradestream_uptime_seconds Time since service start.")
        lines.append("# TYPE tradestream_uptime_seconds gauge")
        lines.append(f"tradestream_uptime_seconds {uptime}")

        # Request count
        lines.append("# HELP tradestream_http_requests_total Total HTTP requests.")
        lines.append("# TYPE tradestream_http_requests_total counter")
        lines.append(f"tradestream_http_requests_total {_metrics['request_count']}")

        # Latency percentiles
        percentiles = _compute_percentiles(_metrics["api_latencies"])
        lines.append("# HELP tradestream_http_request_duration_ms HTTP request latency in milliseconds.")
        lines.append("# TYPE tradestream_http_request_duration_ms gauge")
        lines.append(f'tradestream_http_request_duration_ms{{quantile="0.5"}} {percentiles["p50"]}')
        lines.append(f'tradestream_http_request_duration_ms{{quantile="0.9"}} {percentiles["p90"]}')
        lines.append(f'tradestream_http_request_duration_ms{{quantile="0.99"}} {percentiles["p99"]}')

        # DB/Redis/Exchange status (1=ok, 0=down)
        try:
            deps = await check_deps()
        except Exception:
            deps = {"postgres": "error", "redis": "error", "exchange": "error"}

        lines.append("# HELP tradestream_dependency_up Whether a dependency is healthy (1=up, 0=down).")
        lines.append("# TYPE tradestream_dependency_up gauge")
        for dep, status in deps.items():
            val = 1 if status in ("ok", "not_configured") else 0
            lines.append(f'tradestream_dependency_up{{dependency="{dep}"}} {val}')

        # Query DB metrics
        try:
            async with db_pool.acquire() as conn:
                active_strategies = await conn.fetchval(
                    "SELECT COUNT(*) FROM strategy_specs WHERE source != 'DISABLED'"
                ) or 0
                open_positions = await conn.fetchval(
                    "SELECT COUNT(*) FROM paper_portfolio WHERE quantity != 0"
                ) or 0
                signals_per_hour = await conn.fetchval(
                    "SELECT COUNT(*) FROM signals "
                    "WHERE created_at > NOW() - INTERVAL '1 hour'"
                ) or 0

            lines.append("# HELP tradestream_active_strategies Number of active strategies.")
            lines.append("# TYPE tradestream_active_strategies gauge")
            lines.append(f"tradestream_active_strategies {active_strategies}")

            lines.append("# HELP tradestream_open_positions Number of open positions.")
            lines.append("# TYPE tradestream_open_positions gauge")
            lines.append(f"tradestream_open_positions {open_positions}")

            lines.append("# HELP tradestream_signals_per_hour Signals generated in the last hour.")
            lines.append("# TYPE tradestream_signals_per_hour gauge")
            lines.append(f"tradestream_signals_per_hour {signals_per_hour}")
        except Exception as e:
            logger.warning("Failed to query DB metrics for Prometheus: %s", e)

        lines.append("")
        return PlainTextResponse(
            content="\n".join(lines),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app
