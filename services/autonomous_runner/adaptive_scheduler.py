"""Adaptive scheduling with latency tracking.

Tracks P95/P99 latencies and adjusts batch size and timeouts
to maintain pipeline throughput within the 60-second cycle budget.
"""

import bisect
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveState:
    """Current adaptive scheduler state."""

    batch_size: int = 10
    symbol_timeout_seconds: float = 10.0
    should_skip_cycle: bool = False
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    sample_count: int = 0


class AdaptiveScheduler:
    """Adjusts batch size and timeouts based on observed latency.

    Rules from spec:
    - If P95 > 8000ms: reduce batch size from 10 to 5, extend timeout to 15s
    - If P99 > 9000ms: skip entire cycle
    - Track latencies in a rolling window
    """

    def __init__(
        self,
        window_size: int = 50,
        p95_threshold_ms: float = 8000.0,
        p99_threshold_ms: float = 9000.0,
        default_batch_size: int = 10,
        reduced_batch_size: int = 5,
        default_timeout: float = 10.0,
        extended_timeout: float = 15.0,
    ):
        self._window_size = window_size
        self._p95_threshold = p95_threshold_ms
        self._p99_threshold = p99_threshold_ms
        self._default_batch_size = default_batch_size
        self._reduced_batch_size = reduced_batch_size
        self._default_timeout = default_timeout
        self._extended_timeout = extended_timeout
        self._latencies: list = []  # sorted for percentile calculation

    def record_latency(self, latency_ms: float):
        """Record a symbol processing latency."""
        bisect.insort(self._latencies, latency_ms)
        if len(self._latencies) > self._window_size:
            self._latencies.pop(0)

    def get_state(self) -> AdaptiveState:
        """Compute the current adaptive state based on observed latencies."""
        n = len(self._latencies)
        if n < 3:
            return AdaptiveState(
                batch_size=self._default_batch_size,
                symbol_timeout_seconds=self._default_timeout,
                sample_count=n,
            )

        p95 = self._latencies[int(n * 0.95)]
        p99 = self._latencies[int(n * 0.99)]

        skip = p99 > self._p99_threshold
        high_latency = p95 > self._p95_threshold

        if skip:
            logger.warning(
                "P99 latency %.0fms > %.0fms, recommending cycle skip",
                p99,
                self._p99_threshold,
            )

        if high_latency:
            logger.info(
                "P95 latency %.0fms > %.0fms, reducing batch size and extending timeout",
                p95,
                self._p95_threshold,
            )

        return AdaptiveState(
            batch_size=self._reduced_batch_size if high_latency else self._default_batch_size,
            symbol_timeout_seconds=self._extended_timeout if high_latency else self._default_timeout,
            should_skip_cycle=skip,
            p95_ms=p95,
            p99_ms=p99,
            sample_count=n,
        )

    def reset(self):
        """Clear latency history."""
        self._latencies.clear()
