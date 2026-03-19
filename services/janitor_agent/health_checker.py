"""Health check aggregator for TradeStream services.

Polls health endpoints of all registered services and aggregates results.
Generates alerts when services are unhealthy.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests
from absl import logging


@dataclass
class ServiceHealth:
    """Health status for a single service."""

    service_name: str
    url: str
    healthy: bool
    status_code: Optional[int] = None
    response_time_ms: int = 0
    error: Optional[str] = None
    checked_at: Optional[datetime] = None


@dataclass
class HealthCheckConfig:
    """Configuration for health check aggregation."""

    timeout_seconds: int = 5
    services: dict[str, str] = field(
        default_factory=lambda: {
            "market-data-api": "http://market-data-api:8080/health",
            "strategy-api": "http://strategy-api:8080/health",
            "signal-quality": "http://signal-quality:8080/health",
            "opportunity-scoring": "http://opportunity-scoring:8080/health",
            "learning-engine": "http://learning-engine:8080/health",
            "notification-service": "http://notification-service:8080/health",
            "backtesting": "http://backtesting:8080/health",
            "paper-trading": "http://paper-trading:8080/health",
            "strategy-db-mcp": "http://strategy-db-mcp:8080/health",
            "market-mcp": "http://market-mcp:8080/health",
            "signal-mcp": "http://signal-mcp:8080/health",
        }
    )


class HealthChecker:
    """Aggregates health checks across all TradeStream services."""

    def __init__(self, config: HealthCheckConfig):
        self._config = config

    def check_service(self, name: str, url: str) -> ServiceHealth:
        """Check health of a single service."""
        start = time.time()
        try:
            resp = requests.get(url, timeout=self._config.timeout_seconds)
            elapsed = int((time.time() - start) * 1000)
            healthy = resp.status_code == 200
            return ServiceHealth(
                service_name=name,
                url=url,
                healthy=healthy,
                status_code=resp.status_code,
                response_time_ms=elapsed,
                checked_at=datetime.now(timezone.utc),
            )
        except requests.exceptions.Timeout:
            elapsed = int((time.time() - start) * 1000)
            return ServiceHealth(
                service_name=name,
                url=url,
                healthy=False,
                response_time_ms=elapsed,
                error="Timeout",
                checked_at=datetime.now(timezone.utc),
            )
        except requests.exceptions.ConnectionError as e:
            elapsed = int((time.time() - start) * 1000)
            return ServiceHealth(
                service_name=name,
                url=url,
                healthy=False,
                response_time_ms=elapsed,
                error=f"Connection error: {e}",
                checked_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ServiceHealth(
                service_name=name,
                url=url,
                healthy=False,
                response_time_ms=elapsed,
                error=str(e),
                checked_at=datetime.now(timezone.utc),
            )

    def check_all(self) -> list[ServiceHealth]:
        """Check health of all configured services."""
        results = []
        for name, url in self._config.services.items():
            result = self.check_service(name, url)
            if result.healthy:
                logging.info("Service %s healthy (%dms)", name, result.response_time_ms)
            else:
                logging.warning(
                    "Service %s unhealthy: %s",
                    name,
                    result.error or f"HTTP {result.status_code}",
                )
            results.append(result)
        return results

    @staticmethod
    def summarize(results: list[ServiceHealth]) -> dict:
        """Summarize health check results."""
        healthy = [r for r in results if r.healthy]
        unhealthy = [r for r in results if not r.healthy]
        avg_response_ms = (
            sum(r.response_time_ms for r in results) / len(results) if results else 0
        )
        return {
            "total": len(results),
            "healthy": len(healthy),
            "unhealthy": len(unhealthy),
            "avg_response_ms": round(avg_response_ms),
            "unhealthy_services": [
                {"name": r.service_name, "error": r.error or f"HTTP {r.status_code}"}
                for r in unhealthy
            ],
        }
