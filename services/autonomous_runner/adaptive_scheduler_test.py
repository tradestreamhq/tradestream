"""Tests for the adaptive scheduler module."""

import pytest

from services.autonomous_runner.adaptive_scheduler import AdaptiveScheduler


def test_default_state_with_no_data():
    scheduler = AdaptiveScheduler()
    state = scheduler.get_state()
    assert state.batch_size == 10
    assert state.symbol_timeout_seconds == 10.0
    assert state.should_skip_cycle is False
    assert state.sample_count == 0


def test_normal_latency_keeps_defaults():
    scheduler = AdaptiveScheduler(window_size=10)
    for _ in range(10):
        scheduler.record_latency(2000)  # 2 seconds
    state = scheduler.get_state()
    assert state.batch_size == 10
    assert state.symbol_timeout_seconds == 10.0
    assert state.should_skip_cycle is False
    assert state.p95_ms == 2000


def test_high_p95_reduces_batch_size():
    scheduler = AdaptiveScheduler(
        window_size=20,
        p95_threshold_ms=8000,
        reduced_batch_size=5,
        extended_timeout=15.0,
    )
    # Fill with high latency values
    for _ in range(20):
        scheduler.record_latency(9000)
    state = scheduler.get_state()
    assert state.batch_size == 5
    assert state.symbol_timeout_seconds == 15.0
    assert state.should_skip_cycle is False  # P99 is 9000, not > 9000


def test_extreme_p99_recommends_skip():
    scheduler = AdaptiveScheduler(
        window_size=20,
        p99_threshold_ms=9000,
    )
    for _ in range(20):
        scheduler.record_latency(10000)
    state = scheduler.get_state()
    assert state.should_skip_cycle is True


def test_mixed_latencies():
    scheduler = AdaptiveScheduler(window_size=20, p95_threshold_ms=8000)
    # Mostly fast, some slow
    for _ in range(15):
        scheduler.record_latency(1000)
    for _ in range(5):
        scheduler.record_latency(5000)
    state = scheduler.get_state()
    assert state.batch_size == 10  # P95 should be ~5000, below 8000
    assert state.should_skip_cycle is False


def test_reset_clears_history():
    scheduler = AdaptiveScheduler(window_size=10)
    for _ in range(10):
        scheduler.record_latency(9000)
    scheduler.reset()
    state = scheduler.get_state()
    assert state.sample_count == 0
    assert state.batch_size == 10


def test_window_size_trimming():
    scheduler = AdaptiveScheduler(window_size=5)
    for i in range(10):
        scheduler.record_latency(float(i * 1000))
    state = scheduler.get_state()
    assert state.sample_count == 5
