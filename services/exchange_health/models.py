"""Data models for exchange health monitoring."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


class AlertLevel(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class LatencyStats:
    samples: List[float] = field(default_factory=list)
    max_samples: int = 100

    def record(self, latency_ms: float) -> None:
        self.samples.append(latency_ms)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples :]

    @property
    def avg(self) -> float:
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * p / 100)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]


@dataclass
class RateLimitInfo:
    remaining: int = 0
    total: int = 0

    @property
    def usage_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return (1 - self.remaining / self.total) * 100


@dataclass
class Alert:
    exchange: str
    level: AlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
        }


@dataclass
class ExchangeHealth:
    exchange_id: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    latency: LatencyStats = field(default_factory=LatencyStats)
    rate_limit: RateLimitInfo = field(default_factory=RateLimitInfo)
    last_error: Optional[str] = None
    last_check: float = 0.0
    baseline_latency: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "status": self.status.value,
            "latency_ms": {
                "avg": round(self.latency.avg, 2),
                "p95": round(self.latency.p95, 2),
                "p99": round(self.latency.p99, 2),
            },
            "rate_limit": {
                "remaining": self.rate_limit.remaining,
                "total": self.rate_limit.total,
                "usage_pct": round(self.rate_limit.usage_pct, 1),
            },
            "last_error": self.last_error,
            "last_check": self.last_check,
        }
