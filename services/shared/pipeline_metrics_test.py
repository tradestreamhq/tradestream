"""Tests for pipeline metrics collection."""

import threading

import pytest

from services.shared.pipeline_metrics import (
    Counter,
    Gauge,
    Histogram,
    PipelineMetrics,
)


class TestCounter:
    def test_initial_value(self):
        c = Counter()
        assert c.value == 0

    def test_increment(self):
        c = Counter()
        c.inc()
        assert c.value == 1

    def test_increment_by_amount(self):
        c = Counter()
        c.inc(5)
        assert c.value == 5

    def test_thread_safety(self):
        c = Counter()
        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: [c.inc() for _ in range(100)])
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert c.value == 1000


class TestGauge:
    def test_initial_value(self):
        g = Gauge()
        assert g.value == 0.0

    def test_set(self):
        g = Gauge()
        g.set(42.5)
        assert g.value == 42.5

    def test_inc_dec(self):
        g = Gauge()
        g.inc(3)
        g.dec(1)
        assert g.value == 2


class TestHistogram:
    def test_empty(self):
        h = Histogram()
        assert h.count == 0
        assert h.percentile(50) == 0.0

    def test_observe(self):
        h = Histogram()
        for v in [10, 20, 30, 40, 50]:
            h.observe(v)
        assert h.count == 5
        assert h.sum == 150.0

    def test_percentiles(self):
        h = Histogram()
        for v in range(1, 101):
            h.observe(v)
        p50 = h.percentile(50)
        p99 = h.percentile(99)
        assert 49 <= p50 <= 51
        assert 98 <= p99 <= 100

    def test_to_dict(self):
        h = Histogram()
        h.observe(100)
        d = h.to_dict()
        assert d["count"] == 1
        assert d["sum"] == 100.0
        assert "p50" in d
        assert "p90" in d
        assert "p99" in d

    def test_sliding_window(self):
        h = Histogram(max_size=5)
        for v in range(10):
            h.observe(v)
        assert h.count == 10
        # Only last 5 samples should be in the window for percentiles
        p50 = h.percentile(50)
        assert p50 >= 5  # Values 5-9 in window


class TestPipelineMetrics:
    def test_snapshot_structure(self):
        m = PipelineMetrics()
        snap = m.snapshot()
        assert "signal_generation" in snap
        assert "delivery" in snap
        assert "dead_letter_queue" in snap
        assert "telegram" in snap
        assert "stripe_webhooks" in snap
        assert "active_subscribers" in snap

    def test_delivery_success_rate_no_attempts(self):
        m = PipelineMetrics()
        assert m.delivery_success_rate() == 1.0

    def test_delivery_success_rate(self):
        m = PipelineMetrics()
        for _ in range(8):
            m.deliveries_attempted.inc()
            m.deliveries_succeeded.inc()
        for _ in range(2):
            m.deliveries_attempted.inc()
            m.deliveries_failed.inc()
        rate = m.delivery_success_rate()
        assert abs(rate - 0.8) < 0.01

    def test_channel_metrics(self):
        m = PipelineMetrics()
        m.record_channel_success("telegram")
        m.record_channel_success("telegram")
        m.record_channel_failure("webhook")
        snap = m.snapshot()
        assert snap["delivery"]["by_channel"]["telegram"]["success"] == 2
        assert snap["delivery"]["by_channel"]["webhook"]["failure"] == 1

    def test_signal_generation_metrics(self):
        m = PipelineMetrics()
        m.signals_generated.inc()
        m.signal_generation_errors.inc()
        m.signal_generation_latency_ms.observe(150.0)
        snap = m.snapshot()
        assert snap["signal_generation"]["total"] == 1
        assert snap["signal_generation"]["errors"] == 1

    def test_telegram_metrics(self):
        m = PipelineMetrics()
        m.telegram_api_calls.inc()
        m.telegram_api_errors.inc()
        m.telegram_circuit_breaker_trips.inc()
        snap = m.snapshot()
        assert snap["telegram"]["api_calls"] == 1
        assert snap["telegram"]["api_errors"] == 1
        assert snap["telegram"]["circuit_breaker_trips"] == 1

    def test_stripe_webhook_metrics(self):
        m = PipelineMetrics()
        m.stripe_webhooks_received.inc()
        m.stripe_webhooks_processed.inc()
        snap = m.snapshot()
        assert snap["stripe_webhooks"]["received"] == 1
        assert snap["stripe_webhooks"]["processed"] == 1
