"""Tests for the token bucket rate limiter and rate limiter service."""

import asyncio
import unittest

from services.rate_limiter.limiter import (
    ExchangeRateLimiter,
    RateLimiterService,
    TokenBucket,
)
from services.rate_limiter.models import (
    ExchangeRateConfig,
    RateLimitedRequest,
    RequestPriority,
)


class TokenBucketTest(unittest.TestCase):
    def test_initial_tokens(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        self.assertAlmostEqual(bucket.available_tokens, 10.0, places=1)

    def test_consume_tokens(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        self.assertTrue(bucket.try_consume(5.0))
        self.assertAlmostEqual(bucket.available_tokens, 5.0, places=1)

    def test_consume_fails_when_insufficient(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        self.assertTrue(bucket.try_consume(10.0))
        self.assertFalse(bucket.try_consume(1.0))

    def test_time_until_available(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        bucket.try_consume(10.0)
        wait = bucket.time_until_available(5.0)
        self.assertGreater(wait, 0.0)
        self.assertAlmostEqual(wait, 0.5, places=1)

    def test_time_until_available_when_enough(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        self.assertEqual(bucket.time_until_available(1.0), 0.0)

    def test_utilization_starts_at_zero(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        self.assertAlmostEqual(bucket.utilization_pct, 0.0, places=1)

    def test_utilization_after_consumption(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        bucket.try_consume(10.0)
        self.assertAlmostEqual(bucket.utilization_pct, 100.0, places=0)


class ExchangeRateLimiterTest(unittest.TestCase):
    def _make_limiter(self, rps=10.0, rpm=600.0):
        config = ExchangeRateConfig(
            exchange_id="test_exchange",
            requests_per_second=rps,
            requests_per_minute=rpm,
        )
        return ExchangeRateLimiter(config)

    def test_try_acquire_succeeds(self):
        limiter = self._make_limiter()
        self.assertTrue(limiter.try_acquire())

    def test_try_acquire_exhaustion(self):
        limiter = self._make_limiter(rps=2.0, rpm=600.0)
        self.assertTrue(limiter.try_acquire())
        self.assertTrue(limiter.try_acquire())
        self.assertFalse(limiter.try_acquire())

    def test_metrics_tracking(self):
        limiter = self._make_limiter(rps=1.0, rpm=600.0)
        limiter.try_acquire()
        limiter.try_acquire()  # This should be throttled
        metrics = limiter.metrics
        self.assertEqual(metrics.total_requests, 2)
        self.assertEqual(metrics.throttled_requests, 1)

    def test_enqueue_and_queue_size(self):
        limiter = self._make_limiter()
        req = RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="q1")
        limiter.enqueue(req)
        self.assertEqual(limiter.queue_size, 1)

    def test_async_acquire(self):
        limiter = self._make_limiter(rps=100.0, rpm=6000.0)
        asyncio.get_event_loop().run_until_complete(limiter.acquire())
        self.assertEqual(limiter.metrics.total_requests, 1)

    def test_process_queue(self):
        limiter = self._make_limiter(rps=100.0, rpm=6000.0)
        results = []
        for i in range(3):
            req = RateLimitedRequest(
                priority=RequestPriority.DATA_REQUEST,
                request_id=f"q{i}",
                callback=lambda i=i: results.append(i),
            )
            limiter.enqueue(req)

        asyncio.get_event_loop().run_until_complete(limiter.process_queue())
        self.assertEqual(len(results), 3)


class ExchangeRateLimiterWeightTest(unittest.TestCase):
    def test_weight_based_limiting(self):
        config = ExchangeRateConfig(
            exchange_id="weighted",
            requests_per_second=100.0,
            requests_per_minute=6000.0,
            weight_per_second=10.0,
            weight_per_minute=600.0,
        )
        limiter = ExchangeRateLimiter(config)
        # Use up all weight in one heavy request
        self.assertTrue(limiter.try_acquire(weight=10))
        # Next request should be throttled by weight
        self.assertFalse(limiter.try_acquire(weight=1))


class RateLimiterServiceTest(unittest.TestCase):
    def _make_service(self):
        svc = RateLimiterService()
        svc.register_exchange(ExchangeRateConfig(exchange_id="binance", requests_per_second=20.0))
        svc.register_exchange(ExchangeRateConfig(exchange_id="kraken", requests_per_second=10.0))
        return svc

    def test_register_and_list(self):
        svc = self._make_service()
        self.assertIn("binance", svc.registered_exchanges)
        self.assertIn("kraken", svc.registered_exchanges)

    def test_try_acquire_per_exchange(self):
        svc = self._make_service()
        self.assertTrue(svc.try_acquire("binance"))
        self.assertTrue(svc.try_acquire("kraken"))

    def test_unknown_exchange_raises(self):
        svc = self._make_service()
        with self.assertRaises(KeyError):
            svc.try_acquire("unknown_exchange")

    def test_get_metrics(self):
        svc = self._make_service()
        svc.try_acquire("binance")
        metrics = svc.get_metrics("binance")
        self.assertEqual(metrics.total_requests, 1)

    def test_get_all_metrics(self):
        svc = self._make_service()
        svc.try_acquire("binance")
        svc.try_acquire("kraken")
        all_metrics = svc.get_all_metrics()
        self.assertIn("binance", all_metrics)
        self.assertIn("kraken", all_metrics)

    def test_async_acquire(self):
        svc = self._make_service()
        asyncio.get_event_loop().run_until_complete(svc.acquire("binance"))
        self.assertEqual(svc.get_metrics("binance").total_requests, 1)

    def test_independent_exchange_limits(self):
        """Exhausting one exchange does not affect another."""
        svc = RateLimiterService()
        svc.register_exchange(ExchangeRateConfig(exchange_id="small", requests_per_second=1.0))
        svc.register_exchange(ExchangeRateConfig(exchange_id="large", requests_per_second=100.0))

        svc.try_acquire("small")
        self.assertFalse(svc.try_acquire("small"))  # Exhausted
        self.assertTrue(svc.try_acquire("large"))  # Independent


if __name__ == "__main__":
    unittest.main()
