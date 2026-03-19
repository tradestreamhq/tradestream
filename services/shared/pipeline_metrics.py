"""Pipeline metrics collection for signal generation, delivery, and billing.

Thread-safe in-memory metrics with JSON export for structured logging.
Tracks counters, gauges, and latency histograms across the signal pipeline.
"""

import threading
import time
from collections import defaultdict, deque


class Counter:
    """Thread-safe monotonic counter."""

    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def inc(self, amount=1):
        with self._lock:
            self._value += amount

    @property
    def value(self):
        return self._value


class Gauge:
    """Thread-safe gauge (can go up or down)."""

    def __init__(self):
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value):
        with self._lock:
            self._value = value

    def inc(self, amount=1):
        with self._lock:
            self._value += amount

    def dec(self, amount=1):
        with self._lock:
            self._value -= amount

    @property
    def value(self):
        return self._value


class Histogram:
    """Thread-safe latency histogram with percentile computation.

    Keeps a sliding window of the most recent observations.
    """

    def __init__(self, max_size=1000):
        self._samples = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._count = 0
        self._sum = 0.0

    def observe(self, value):
        with self._lock:
            self._samples.append(value)
            self._count += 1
            self._sum += value

    def percentile(self, p):
        """Return the p-th percentile (0-100) of recent samples."""
        with self._lock:
            if not self._samples:
                return 0.0
            sorted_samples = sorted(self._samples)
            idx = int(len(sorted_samples) * p / 100)
            idx = min(idx, len(sorted_samples) - 1)
            return sorted_samples[idx]

    @property
    def count(self):
        return self._count

    @property
    def sum(self):
        return self._sum

    def to_dict(self):
        return {
            "count": self._count,
            "sum": round(self._sum, 2),
            "p50": round(self.percentile(50), 2),
            "p90": round(self.percentile(90), 2),
            "p99": round(self.percentile(99), 2),
        }


class PipelineMetrics:
    """Centralized metrics for the signal pipeline.

    Usage:
        metrics = PipelineMetrics()
        metrics.signals_generated.inc()
        metrics.delivery_latency_ms.observe(120.5)
        snapshot = metrics.snapshot()
    """

    def __init__(self):
        # Signal generation
        self.signals_generated = Counter()
        self.signal_generation_errors = Counter()
        self.signal_generation_latency_ms = Histogram()

        # Signal delivery
        self.deliveries_attempted = Counter()
        self.deliveries_succeeded = Counter()
        self.deliveries_failed = Counter()
        self.delivery_latency_ms = Histogram()

        # Per-channel delivery
        self._channel_success = defaultdict(Counter)
        self._channel_failure = defaultdict(Counter)

        # Dead letter queue
        self.dlq_enqueued = Counter()
        self.dlq_retried = Counter()
        self.dlq_exhausted = Counter()

        # Telegram-specific
        self.telegram_api_calls = Counter()
        self.telegram_api_errors = Counter()
        self.telegram_api_latency_ms = Histogram()
        self.telegram_circuit_breaker_trips = Counter()

        # Billing / Stripe webhooks
        self.stripe_webhooks_received = Counter()
        self.stripe_webhooks_processed = Counter()
        self.stripe_webhooks_failed = Counter()
        self.stripe_webhook_latency_ms = Histogram()

        # Active subscribers gauge
        self.active_subscribers = Gauge()

    def record_channel_success(self, channel: str):
        self._channel_success[channel].inc()

    def record_channel_failure(self, channel: str):
        self._channel_failure[channel].inc()

    def delivery_success_rate(self) -> float:
        """Return delivery success rate as a fraction (0.0 - 1.0)."""
        total = self.deliveries_attempted.value
        if total == 0:
            return 1.0
        return self.deliveries_succeeded.value / total

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of all metrics."""
        channel_stats = {}
        all_channels = set(self._channel_success.keys()) | set(
            self._channel_failure.keys()
        )
        for ch in all_channels:
            channel_stats[ch] = {
                "success": self._channel_success[ch].value,
                "failure": self._channel_failure[ch].value,
            }

        return {
            "signal_generation": {
                "total": self.signals_generated.value,
                "errors": self.signal_generation_errors.value,
                "latency_ms": self.signal_generation_latency_ms.to_dict(),
            },
            "delivery": {
                "attempted": self.deliveries_attempted.value,
                "succeeded": self.deliveries_succeeded.value,
                "failed": self.deliveries_failed.value,
                "success_rate": round(self.delivery_success_rate(), 4),
                "latency_ms": self.delivery_latency_ms.to_dict(),
                "by_channel": channel_stats,
            },
            "dead_letter_queue": {
                "enqueued": self.dlq_enqueued.value,
                "retried": self.dlq_retried.value,
                "exhausted": self.dlq_exhausted.value,
            },
            "telegram": {
                "api_calls": self.telegram_api_calls.value,
                "api_errors": self.telegram_api_errors.value,
                "circuit_breaker_trips": self.telegram_circuit_breaker_trips.value,
                "api_latency_ms": self.telegram_api_latency_ms.to_dict(),
            },
            "stripe_webhooks": {
                "received": self.stripe_webhooks_received.value,
                "processed": self.stripe_webhooks_processed.value,
                "failed": self.stripe_webhooks_failed.value,
                "latency_ms": self.stripe_webhook_latency_ms.to_dict(),
            },
            "active_subscribers": self.active_subscribers.value,
        }
