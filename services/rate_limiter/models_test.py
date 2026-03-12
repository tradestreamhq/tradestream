"""Tests for rate limiter models."""

import unittest

from services.rate_limiter.models import (
    ExchangeRateConfig,
    RateLimitedRequest,
    RequestPriority,
    UsageMetrics,
)


class RequestPriorityTest(unittest.TestCase):
    def test_priority_ordering(self):
        self.assertLess(RequestPriority.MARKET_ORDER, RequestPriority.LIMIT_ORDER)
        self.assertLess(RequestPriority.LIMIT_ORDER, RequestPriority.ACCOUNT_DATA)
        self.assertLess(RequestPriority.ACCOUNT_DATA, RequestPriority.DATA_REQUEST)


class ExchangeRateConfigTest(unittest.TestCase):
    def test_default_config(self):
        config = ExchangeRateConfig(exchange_id="binance")
        self.assertEqual(config.exchange_id, "binance")
        self.assertEqual(config.requests_per_second, 10.0)
        self.assertEqual(config.requests_per_minute, 600.0)
        self.assertEqual(config.weight_per_second, 0.0)

    def test_custom_config(self):
        config = ExchangeRateConfig(
            exchange_id="kraken",
            requests_per_second=5.0,
            requests_per_minute=300.0,
            weight_per_second=20.0,
            weight_per_minute=1200.0,
        )
        self.assertEqual(config.requests_per_second, 5.0)
        self.assertEqual(config.weight_per_minute, 1200.0)

    def test_invalid_rps_raises(self):
        with self.assertRaises(ValueError):
            ExchangeRateConfig(exchange_id="bad", requests_per_second=0)

    def test_invalid_rpm_raises(self):
        with self.assertRaises(ValueError):
            ExchangeRateConfig(exchange_id="bad", requests_per_minute=-1)


class RateLimitedRequestTest(unittest.TestCase):
    def test_ordering_by_priority(self):
        market = RateLimitedRequest(priority=RequestPriority.MARKET_ORDER)
        data = RateLimitedRequest(priority=RequestPriority.DATA_REQUEST)
        self.assertLess(market, data)

    def test_default_weight(self):
        req = RateLimitedRequest(priority=RequestPriority.DATA_REQUEST)
        self.assertEqual(req.weight, 1)


class UsageMetricsTest(unittest.TestCase):
    def test_throttled_pct_zero(self):
        m = UsageMetrics(exchange_id="test")
        self.assertEqual(m.throttled_pct, 0.0)

    def test_throttled_pct(self):
        m = UsageMetrics(exchange_id="test", total_requests=100, throttled_requests=25)
        self.assertAlmostEqual(m.throttled_pct, 25.0)

    def test_avg_wait_time_zero(self):
        m = UsageMetrics(exchange_id="test")
        self.assertEqual(m.avg_wait_time_ms, 0.0)

    def test_avg_wait_time(self):
        m = UsageMetrics(
            exchange_id="test",
            throttled_requests=10,
            total_wait_time_ms=500.0,
        )
        self.assertAlmostEqual(m.avg_wait_time_ms, 50.0)


if __name__ == "__main__":
    unittest.main()
