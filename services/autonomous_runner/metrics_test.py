"""Tests for the metrics module."""

import pytest

from services.autonomous_runner.metrics import PipelineMetrics


def test_record_signal_generated():
    metrics = PipelineMetrics()
    metrics.record_signal_generated("BTC-USD", "BUY")
    assert metrics._in_memory["generated:BTC-USD:BUY"] == 1.0
    metrics.record_signal_generated("BTC-USD", "BUY")
    assert metrics._in_memory["generated:BTC-USD:BUY"] == 2.0


def test_record_signal_emitted():
    metrics = PipelineMetrics()
    metrics.record_signal_emitted("ETH-USD", "SELL")
    assert metrics._in_memory["emitted:ETH-USD:SELL"] == 1.0


def test_record_signal_rejected():
    metrics = PipelineMetrics()
    metrics.record_signal_rejected("SOL-USD", "low_confidence")
    assert metrics._in_memory["rejected:SOL-USD:low_confidence"] == 1.0


def test_record_signal_skipped():
    metrics = PipelineMetrics()
    metrics.record_signal_skipped("kill_switch")
    assert metrics._in_memory["skipped:kill_switch"] == 1.0


def test_record_cycle_duration():
    metrics = PipelineMetrics()
    metrics.record_cycle_duration(5.0)
    metrics.record_cycle_duration(10.0)
    assert metrics._in_memory["cycle_count"] == 2.0
    assert len(metrics._histograms["cycle_duration"]) == 2


def test_record_tool_retry():
    metrics = PipelineMetrics()
    metrics.record_tool_retry("get_top_strategies", "strategy")
    assert metrics._in_memory["retry:get_top_strategies:strategy"] == 1.0


def test_get_summary():
    metrics = PipelineMetrics()
    metrics.record_cycle_duration(5.0)
    metrics.record_cycle_duration(10.0)
    metrics.record_cycle_duration(15.0)

    summary = metrics.get_summary()
    assert summary["total_cycles"] == 3
    assert summary["cycle_duration_avg_seconds"] == 10.0
    assert summary["cycle_duration_p95_seconds"] > 0


def test_get_summary_empty():
    metrics = PipelineMetrics()
    summary = metrics.get_summary()
    assert summary["total_cycles"] == 0
    assert summary["cycle_duration_avg_seconds"] == 0


def test_histogram_window_limit():
    metrics = PipelineMetrics()
    for i in range(150):
        metrics.record_cycle_duration(float(i))
    assert len(metrics._histograms["cycle_duration"]) == 100
