"""Tests for the Exchange Health REST API."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.exchange_health.app import create_app
from services.exchange_health.models import (
    Alert,
    AlertLevel,
    ConnectionStatus,
    ExchangeHealth,
    LatencyStats,
    RateLimitInfo,
)
from services.exchange_health.monitor import ExchangeHealthMonitor


def _make_monitor(exchange_ids=None):
    """Create a monitor with mock exchanges."""
    if exchange_ids is None:
        exchange_ids = ["coinbasepro", "binance"]
    exchanges = {eid: MagicMock() for eid in exchange_ids}
    monitor = ExchangeHealthMonitor(exchanges, check_interval=60)
    return monitor


@pytest.fixture
def client():
    monitor = _make_monitor()
    app = create_app(monitor)
    return TestClient(app, raise_server_exceptions=False), monitor


class TestHealthEndpoints:
    def test_health(self, client):
        tc, monitor = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestExchangeHealthEndpoints:
    def test_get_health_summary(self, client):
        tc, monitor = client
        resp = tc.get("/health")
        # /health is the service health endpoint
        assert resp.status_code == 200

    def test_get_exchange_health_summary(self, client):
        tc, monitor = client
        resp = tc.get("/health/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "exchange-health-summary"
        attrs = body["data"]["attributes"]
        assert attrs["total"] == 2
        assert attrs["disconnected"] == 2  # no checks run yet

    def test_get_exchange_health_detail(self, client):
        tc, monitor = client
        resp = tc.get("/health/coinbasepro")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "coinbasepro"
        assert body["data"]["attributes"]["exchange_id"] == "coinbasepro"

    def test_get_exchange_health_not_found(self, client):
        tc, monitor = client
        resp = tc.get("/health/unknown_exchange")
        assert resp.status_code == 404

    def test_get_alerts_empty(self, client):
        tc, monitor = client
        resp = tc.get("/health/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_trigger_check(self, client):
        tc, monitor = client
        # Mock the exchange's fetch_time to succeed
        monitor._exchanges["coinbasepro"].fetch_time.return_value = 1234567890
        resp = tc.post("/health/coinbasepro/check")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "connected"

    def test_trigger_check_not_found(self, client):
        tc, monitor = client
        resp = tc.post("/health/nonexistent/check")
        assert resp.status_code == 404


class TestModels:
    def test_latency_stats(self):
        stats = LatencyStats()
        for i in range(20):
            stats.record(float(i * 10))
        assert stats.avg == 95.0
        assert stats.p95 > 0
        assert stats.p99 > 0

    def test_latency_stats_empty(self):
        stats = LatencyStats()
        assert stats.avg == 0.0
        assert stats.p95 == 0.0

    def test_latency_stats_max_samples(self):
        stats = LatencyStats(max_samples=5)
        for i in range(10):
            stats.record(float(i))
        assert len(stats.samples) == 5

    def test_rate_limit_info(self):
        rl = RateLimitInfo(remaining=20, total=100)
        assert rl.usage_pct == 80.0

    def test_rate_limit_info_zero_total(self):
        rl = RateLimitInfo(remaining=0, total=0)
        assert rl.usage_pct == 0.0

    def test_exchange_health_to_dict(self):
        eh = ExchangeHealth(exchange_id="test")
        d = eh.to_dict()
        assert d["exchange_id"] == "test"
        assert "latency_ms" in d
        assert "rate_limit" in d

    def test_alert_to_dict(self):
        a = Alert(
            exchange="test",
            level=AlertLevel.WARNING,
            message="test alert",
            timestamp=1000.0,
        )
        d = a.to_dict()
        assert d["level"] == "warning"


class TestMetrics:
    def test_check_alerts_disconnected(self):
        from services.exchange_health.metrics import check_alerts

        health = ExchangeHealth(
            exchange_id="test", status=ConnectionStatus.DISCONNECTED
        )
        alerts = check_alerts(health)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_check_alerts_latency_spike(self):
        from services.exchange_health.metrics import check_alerts

        health = ExchangeHealth(exchange_id="test", status=ConnectionStatus.CONNECTED)
        health.baseline_latency = 50.0
        for _ in range(10):
            health.latency.record(150.0)
        alerts = check_alerts(health)
        assert any("Latency spike" in a.message for a in alerts)

    def test_check_alerts_rate_limit(self):
        from services.exchange_health.metrics import check_alerts

        health = ExchangeHealth(exchange_id="test", status=ConnectionStatus.CONNECTED)
        health.rate_limit = RateLimitInfo(remaining=10, total=100)
        alerts = check_alerts(health)
        assert any("Rate limit" in a.message for a in alerts)

    def test_no_alerts_when_healthy(self):
        from services.exchange_health.metrics import check_alerts

        health = ExchangeHealth(exchange_id="test", status=ConnectionStatus.CONNECTED)
        health.rate_limit = RateLimitInfo(remaining=80, total=100)
        alerts = check_alerts(health)
        assert len(alerts) == 0

    def test_aggregate_status(self):
        from services.exchange_health.metrics import aggregate_status

        exchanges = {
            "a": ExchangeHealth("a", status=ConnectionStatus.CONNECTED),
            "b": ExchangeHealth("b", status=ConnectionStatus.DISCONNECTED),
        }
        result = aggregate_status(exchanges)
        assert result["overall"] == "unhealthy"
        assert result["connected"] == 1
        assert result["disconnected"] == 1

    def test_aggregate_status_all_healthy(self):
        from services.exchange_health.metrics import aggregate_status

        exchanges = {
            "a": ExchangeHealth("a", status=ConnectionStatus.CONNECTED),
            "b": ExchangeHealth("b", status=ConnectionStatus.CONNECTED),
        }
        result = aggregate_status(exchanges)
        assert result["overall"] == "healthy"

    def test_update_baseline(self):
        from services.exchange_health.metrics import update_baseline

        health = ExchangeHealth(exchange_id="test")
        for i in range(15):
            health.latency.record(100.0)
        update_baseline(health)
        assert health.baseline_latency is not None


class TestMonitor:
    def test_init(self):
        monitor = _make_monitor()
        assert len(monitor.health) == 2

    def test_get_summary(self):
        monitor = _make_monitor()
        summary = monitor.get_summary()
        assert summary["total"] == 2
        assert "exchanges" in summary
        assert "recent_alerts" in summary

    def test_get_exchange_health_missing(self):
        monitor = _make_monitor()
        assert monitor.get_exchange_health("nonexistent") is None

    @pytest.mark.asyncio
    async def test_check_exchange_success(self):
        monitor = _make_monitor(["test"])
        monitor._exchanges["test"].fetch_time.return_value = 123
        await monitor.check_exchange("test")
        health = monitor.get_exchange_health("test")
        assert health.status == ConnectionStatus.CONNECTED
        assert health.last_error is None

    @pytest.mark.asyncio
    async def test_check_exchange_failure(self):
        monitor = _make_monitor(["test"])
        monitor._exchanges["test"].fetch_time.side_effect = Exception("timeout")
        await monitor.check_exchange("test")
        health = monitor.get_exchange_health("test")
        assert health.status == ConnectionStatus.DISCONNECTED
        assert health.last_error == "timeout"

    @pytest.mark.asyncio
    async def test_check_all(self):
        monitor = _make_monitor(["a", "b"])
        monitor._exchanges["a"].fetch_time.return_value = 1
        monitor._exchanges["b"].fetch_time.return_value = 2
        await monitor.check_all()
        assert monitor.get_exchange_health("a").status == ConnectionStatus.CONNECTED
        assert monitor.get_exchange_health("b").status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_check_generates_alerts(self):
        monitor = _make_monitor(["test"])
        monitor._exchanges["test"].fetch_time.side_effect = Exception("down")
        await monitor.check_exchange("test")
        assert len(monitor.alerts) > 0
        assert monitor.alerts[0].level == AlertLevel.CRITICAL
