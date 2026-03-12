"""Data models for the API rate limiter service."""

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class RequestPriority(enum.IntEnum):
    """Priority levels for queued requests. Lower value = higher priority."""

    MARKET_ORDER = 0
    LIMIT_ORDER = 1
    ACCOUNT_DATA = 2
    DATA_REQUEST = 3


@dataclass
class ExchangeRateConfig:
    """Rate limit configuration for a single exchange."""

    exchange_id: str
    requests_per_second: float = 10.0
    requests_per_minute: float = 600.0
    weight_per_second: float = 0.0  # 0 means weight-based limiting is disabled
    weight_per_minute: float = 0.0

    def __post_init__(self):
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")


@dataclass(order=True)
class RateLimitedRequest:
    """A request waiting in the rate limiter queue."""

    priority: RequestPriority = field(compare=True)
    created_at: float = field(default_factory=time.monotonic, compare=False)
    weight: int = field(default=1, compare=False)
    callback: Optional[Callable[[], Any]] = field(default=None, compare=False, repr=False)
    request_id: str = field(default="", compare=False)


@dataclass
class UsageMetrics:
    """Tracks rate limiter usage metrics for an exchange."""

    exchange_id: str
    total_requests: int = 0
    throttled_requests: int = 0
    total_wait_time_ms: float = 0.0

    @property
    def throttled_pct(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.throttled_requests / self.total_requests) * 100.0

    @property
    def avg_wait_time_ms(self) -> float:
        if self.throttled_requests == 0:
            return 0.0
        return self.total_wait_time_ms / self.throttled_requests
