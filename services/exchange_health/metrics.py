"""Metrics collection for exchange health monitoring."""

import time
from typing import Dict, List

from services.exchange_health.models import (
    Alert,
    AlertLevel,
    ExchangeHealth,
)

LATENCY_SPIKE_MULTIPLIER = 2.0
RATE_LIMIT_WARNING_PCT = 80.0
BASELINE_MIN_SAMPLES = 10


def check_alerts(health: ExchangeHealth) -> List[Alert]:
    """Check an exchange's health state and return any triggered alerts."""
    alerts: List[Alert] = []

    if health.status.value == "disconnected":
        alerts.append(
            Alert(
                exchange=health.exchange_id,
                level=AlertLevel.CRITICAL,
                message=f"Exchange {health.exchange_id} is disconnected",
            )
        )

    if health.baseline_latency and health.latency.avg > 0:
        if health.latency.avg > health.baseline_latency * LATENCY_SPIKE_MULTIPLIER:
            alerts.append(
                Alert(
                    exchange=health.exchange_id,
                    level=AlertLevel.WARNING,
                    message=(
                        f"Latency spike on {health.exchange_id}: "
                        f"{health.latency.avg:.0f}ms "
                        f"(baseline: {health.baseline_latency:.0f}ms)"
                    ),
                )
            )

    if health.rate_limit.total > 0:
        if health.rate_limit.usage_pct >= RATE_LIMIT_WARNING_PCT:
            alerts.append(
                Alert(
                    exchange=health.exchange_id,
                    level=AlertLevel.WARNING,
                    message=(
                        f"Rate limit usage at {health.rate_limit.usage_pct:.0f}% "
                        f"on {health.exchange_id}"
                    ),
                )
            )

    return alerts


def update_baseline(health: ExchangeHealth) -> None:
    """Update the baseline latency from collected samples once we have enough data."""
    if len(health.latency.samples) >= BASELINE_MIN_SAMPLES and health.baseline_latency is None:
        health.baseline_latency = health.latency.avg


def aggregate_status(exchanges: Dict[str, ExchangeHealth]) -> Dict:
    """Produce an aggregate health summary across all exchanges."""
    total = len(exchanges)
    connected = sum(
        1 for e in exchanges.values() if e.status.value == "connected"
    )
    degraded = sum(
        1 for e in exchanges.values() if e.status.value == "degraded"
    )
    disconnected = total - connected - degraded

    if disconnected > 0:
        overall = "unhealthy"
    elif degraded > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "total": total,
        "connected": connected,
        "degraded": degraded,
        "disconnected": disconnected,
    }
