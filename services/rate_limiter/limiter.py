"""Token bucket rate limiter for exchange API requests."""

import asyncio
import time
from typing import Optional

from services.rate_limiter.models import (
    ExchangeRateConfig,
    RateLimitedRequest,
    RequestPriority,
    UsageMetrics,
)
from services.rate_limiter.queue import PriorityRequestQueue


class TokenBucket:
    """Token bucket algorithm for rate limiting.

    Supports both per-second and per-minute limits. Tokens are refilled
    continuously based on elapsed time.
    """

    def __init__(self, rate: float, capacity: float):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def try_consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: float = 1.0) -> float:
        """Returns seconds until the requested tokens will be available."""
        self._refill()
        if self._tokens >= tokens:
            return 0.0
        deficit = tokens - self._tokens
        return deficit / self._rate

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

    @property
    def utilization_pct(self) -> float:
        """Current utilization as a percentage (0-100)."""
        self._refill()
        return ((self._capacity - self._tokens) / self._capacity) * 100.0


class ExchangeRateLimiter:
    """Rate limiter for a single exchange with per-second and per-minute buckets."""

    def __init__(self, config: ExchangeRateConfig):
        self._config = config
        self._second_bucket = TokenBucket(
            rate=config.requests_per_second,
            capacity=config.requests_per_second,
        )
        self._minute_bucket = TokenBucket(
            rate=config.requests_per_minute / 60.0,
            capacity=config.requests_per_minute,
        )
        # Optional weight-based buckets
        self._weight_second_bucket: Optional[TokenBucket] = None
        self._weight_minute_bucket: Optional[TokenBucket] = None
        if config.weight_per_second > 0:
            self._weight_second_bucket = TokenBucket(
                rate=config.weight_per_second,
                capacity=config.weight_per_second,
            )
        if config.weight_per_minute > 0:
            self._weight_minute_bucket = TokenBucket(
                rate=config.weight_per_minute / 60.0,
                capacity=config.weight_per_minute,
            )

        self._queue = PriorityRequestQueue()
        self._metrics = UsageMetrics(exchange_id=config.exchange_id)
        self._processing = False

    @property
    def config(self) -> ExchangeRateConfig:
        return self._config

    @property
    def metrics(self) -> UsageMetrics:
        return self._metrics

    @property
    def queue_size(self) -> int:
        return self._queue.size

    @property
    def utilization_pct(self) -> float:
        """Average utilization across buckets."""
        values = [self._second_bucket.utilization_pct, self._minute_bucket.utilization_pct]
        if self._weight_second_bucket:
            values.append(self._weight_second_bucket.utilization_pct)
        if self._weight_minute_bucket:
            values.append(self._weight_minute_bucket.utilization_pct)
        return sum(values) / len(values)

    def try_acquire(self, weight: int = 1) -> bool:
        """Try to acquire permission for a request. Returns True if allowed."""
        self._metrics.total_requests += 1

        if not self._second_bucket.try_consume(1):
            self._metrics.throttled_requests += 1
            return False
        if not self._minute_bucket.try_consume(1):
            # Put the second token back conceptually by not proceeding
            self._metrics.throttled_requests += 1
            return False

        if self._weight_second_bucket and not self._weight_second_bucket.try_consume(weight):
            self._metrics.throttled_requests += 1
            return False
        if self._weight_minute_bucket and not self._weight_minute_bucket.try_consume(weight):
            self._metrics.throttled_requests += 1
            return False

        return True

    def time_until_available(self, weight: int = 1) -> float:
        """Returns the minimum wait time until a request can proceed."""
        waits = [
            self._second_bucket.time_until_available(1),
            self._minute_bucket.time_until_available(1),
        ]
        if self._weight_second_bucket:
            waits.append(self._weight_second_bucket.time_until_available(weight))
        if self._weight_minute_bucket:
            waits.append(self._weight_minute_bucket.time_until_available(weight))
        return max(waits)

    async def acquire(
        self,
        priority: RequestPriority = RequestPriority.DATA_REQUEST,
        weight: int = 1,
    ) -> None:
        """Acquire permission for a request, waiting if necessary."""
        if self.try_acquire(weight):
            return

        start = time.monotonic()
        while True:
            wait_time = self.time_until_available(weight)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            if self.try_acquire(weight):
                elapsed_ms = (time.monotonic() - start) * 1000.0
                self._metrics.total_wait_time_ms += elapsed_ms
                return

    def enqueue(self, request: RateLimitedRequest) -> None:
        """Add a request to the priority queue."""
        self._queue.push(request)

    async def process_queue(self) -> None:
        """Process queued requests in priority order."""
        if self._processing:
            return
        self._processing = True
        try:
            while not self._queue.is_empty:
                request = self._queue.peek()
                if request is None:
                    break

                wait_time = self.time_until_available(request.weight)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                request = self._queue.pop()
                if request is None:
                    break

                if self.try_acquire(request.weight):
                    if request.callback:
                        result = request.callback()
                        if asyncio.iscoroutine(result):
                            await result
                else:
                    # Re-enqueue if we still can't acquire
                    self._queue.push(request)
                    await asyncio.sleep(0.01)
        finally:
            self._processing = False


class RateLimiterService:
    """Centralized rate limiter managing multiple exchange connections."""

    def __init__(self):
        self._limiters: dict[str, ExchangeRateLimiter] = {}

    def register_exchange(self, config: ExchangeRateConfig) -> None:
        """Register rate limit configuration for an exchange."""
        self._limiters[config.exchange_id] = ExchangeRateLimiter(config)

    def get_limiter(self, exchange_id: str) -> ExchangeRateLimiter:
        """Get the rate limiter for a specific exchange."""
        if exchange_id not in self._limiters:
            raise KeyError(f"Exchange '{exchange_id}' is not registered")
        return self._limiters[exchange_id]

    def try_acquire(self, exchange_id: str, weight: int = 1) -> bool:
        """Try to acquire a rate limit slot for the given exchange."""
        return self.get_limiter(exchange_id).try_acquire(weight)

    async def acquire(
        self,
        exchange_id: str,
        priority: RequestPriority = RequestPriority.DATA_REQUEST,
        weight: int = 1,
    ) -> None:
        """Acquire a rate limit slot, waiting if necessary."""
        await self.get_limiter(exchange_id).acquire(priority, weight)

    def get_metrics(self, exchange_id: str) -> UsageMetrics:
        """Get usage metrics for an exchange."""
        return self.get_limiter(exchange_id).metrics

    def get_all_metrics(self) -> dict[str, UsageMetrics]:
        """Get usage metrics for all registered exchanges."""
        return {eid: limiter.metrics for eid, limiter in self._limiters.items()}

    @property
    def registered_exchanges(self) -> list[str]:
        return list(self._limiters.keys())
