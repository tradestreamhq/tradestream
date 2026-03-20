"""Prometheus metrics for the autonomous signal generation pipeline.

Exposes counters, histograms, and gauges for monitoring signal
generation cycles, latency, risk decisions, and circuit breaker state.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import prometheus_client; fall back to in-memory tracking
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class PipelineMetrics:
    """Tracks pipeline metrics using Prometheus client or in-memory fallback."""

    def __init__(self):
        self._in_memory = defaultdict(float)
        self._histograms = defaultdict(list)

        if PROMETHEUS_AVAILABLE:
            self.signals_generated = Counter(
                "autonomous_signals_generated_total",
                "Total signals generated",
                ["symbol", "action"],
            )
            self.signals_emitted = Counter(
                "autonomous_signals_emitted_total",
                "Signals that passed risk checks and were emitted",
                ["symbol", "action"],
            )
            self.signals_rejected = Counter(
                "autonomous_signals_rejected_total",
                "Signals rejected by risk management",
                ["symbol", "reason"],
            )
            self.signals_skipped = Counter(
                "autonomous_signals_skipped_total",
                "Signals skipped (kill switch, circuit breaker, backpressure)",
                ["reason"],
            )
            self.cycle_duration = Histogram(
                "autonomous_cycle_duration_seconds",
                "Duration of signal generation cycles",
                buckets=[1, 5, 10, 20, 30, 50, 60, 90, 120],
            )
            self.symbol_processing_duration = Histogram(
                "autonomous_symbol_processing_seconds",
                "Duration of processing a single symbol",
                ["symbol"],
                buckets=[0.5, 1, 2, 5, 8, 10, 15],
            )
            self.tool_call_duration = Histogram(
                "autonomous_tool_call_seconds",
                "Duration of MCP tool calls",
                ["tool", "server"],
                buckets=[0.1, 0.25, 0.5, 1, 2, 5],
            )
            self.tool_call_retries = Counter(
                "autonomous_tool_call_retries_total",
                "Tool call retry attempts",
                ["tool", "server"],
            )
            self.circuit_breaker_state = Gauge(
                "autonomous_circuit_breaker_state",
                "Circuit breaker state (0=closed, 1=half_open, 2=open)",
                ["service"],
            )
            self.active_signals = Gauge(
                "autonomous_active_signals",
                "Currently active signal positions",
            )
            self.portfolio_exposure = Gauge(
                "autonomous_portfolio_exposure_pct",
                "Current portfolio exposure percentage",
            )
            self.daily_pnl = Gauge(
                "autonomous_daily_pnl_pct",
                "Daily P&L percentage",
            )
            self.confidence_histogram = Histogram(
                "autonomous_signal_confidence",
                "Distribution of signal confidence scores",
                buckets=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95],
            )
            self.batch_size = Gauge(
                "autonomous_adaptive_batch_size",
                "Current adaptive batch size",
            )
            self.kill_switch_active = Gauge(
                "autonomous_kill_switch_active",
                "Kill switch state (0=inactive, 1=active)",
            )
            self.db_persistence_success = Counter(
                "autonomous_db_persistence_total",
                "Database persistence attempts",
                ["status"],
            )
            self.total_cycles = Counter(
                "autonomous_cycles_total",
                "Total signal generation cycles",
                ["status"],
            )

    def record_signal_generated(self, symbol: str, action: str):
        if PROMETHEUS_AVAILABLE:
            self.signals_generated.labels(symbol=symbol, action=action).inc()
        self._in_memory[f"generated:{symbol}:{action}"] += 1

    def record_signal_emitted(self, symbol: str, action: str):
        if PROMETHEUS_AVAILABLE:
            self.signals_emitted.labels(symbol=symbol, action=action).inc()
        self._in_memory[f"emitted:{symbol}:{action}"] += 1

    def record_signal_rejected(self, symbol: str, reason: str):
        if PROMETHEUS_AVAILABLE:
            self.signals_rejected.labels(symbol=symbol, reason=reason).inc()
        self._in_memory[f"rejected:{symbol}:{reason}"] += 1

    def record_signal_skipped(self, reason: str):
        if PROMETHEUS_AVAILABLE:
            self.signals_skipped.labels(reason=reason).inc()
        self._in_memory[f"skipped:{reason}"] += 1

    def record_cycle_duration(self, duration_seconds: float, status: str = "success"):
        if PROMETHEUS_AVAILABLE:
            self.cycle_duration.observe(duration_seconds)
            self.total_cycles.labels(status=status).inc()
        self._in_memory["cycle_count"] += 1
        self._histograms["cycle_duration"].append(duration_seconds)
        # Keep last 100
        if len(self._histograms["cycle_duration"]) > 100:
            self._histograms["cycle_duration"] = self._histograms["cycle_duration"][-100:]

    def record_symbol_processing(self, symbol: str, duration_seconds: float):
        if PROMETHEUS_AVAILABLE:
            self.symbol_processing_duration.labels(symbol=symbol).observe(duration_seconds)
        self._histograms[f"symbol:{symbol}"].append(duration_seconds)

    def record_tool_call(self, tool: str, server: str, duration_seconds: float):
        if PROMETHEUS_AVAILABLE:
            self.tool_call_duration.labels(tool=tool, server=server).observe(duration_seconds)

    def record_tool_retry(self, tool: str, server: str):
        if PROMETHEUS_AVAILABLE:
            self.tool_call_retries.labels(tool=tool, server=server).inc()
        self._in_memory[f"retry:{tool}:{server}"] += 1

    def set_circuit_breaker_state(self, service: str, state: int):
        if PROMETHEUS_AVAILABLE:
            self.circuit_breaker_state.labels(service=service).set(state)

    def set_active_signals(self, count: int):
        if PROMETHEUS_AVAILABLE:
            self.active_signals.set(count)

    def set_portfolio_exposure(self, pct: float):
        if PROMETHEUS_AVAILABLE:
            self.portfolio_exposure.set(pct)

    def set_daily_pnl(self, pct: float):
        if PROMETHEUS_AVAILABLE:
            self.daily_pnl.set(pct)

    def record_confidence(self, confidence: float):
        if PROMETHEUS_AVAILABLE:
            self.confidence_histogram.observe(confidence)

    def set_batch_size(self, size: int):
        if PROMETHEUS_AVAILABLE:
            self.batch_size.set(size)

    def set_kill_switch(self, active: bool):
        if PROMETHEUS_AVAILABLE:
            self.kill_switch_active.set(1 if active else 0)

    def record_db_persistence(self, success: bool):
        if PROMETHEUS_AVAILABLE:
            self.db_persistence_success.labels(
                status="success" if success else "failure"
            ).inc()

    def get_summary(self) -> dict:
        """Return in-memory metrics summary for dashboard."""
        cycle_durations = self._histograms.get("cycle_duration", [])
        return {
            "total_cycles": int(self._in_memory.get("cycle_count", 0)),
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "cycle_duration_avg_seconds": (
                sum(cycle_durations) / len(cycle_durations)
                if cycle_durations
                else 0
            ),
            "cycle_duration_p95_seconds": (
                sorted(cycle_durations)[int(len(cycle_durations) * 0.95)]
                if len(cycle_durations) >= 2
                else 0
            ),
        }


# Module-level singleton
pipeline_metrics = PipelineMetrics()
