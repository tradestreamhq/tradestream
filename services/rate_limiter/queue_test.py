"""Tests for the priority request queue."""

import unittest

from services.rate_limiter.models import RateLimitedRequest, RequestPriority
from services.rate_limiter.queue import PriorityRequestQueue


class PriorityRequestQueueTest(unittest.TestCase):
    def test_empty_queue(self):
        q = PriorityRequestQueue()
        self.assertTrue(q.is_empty)
        self.assertEqual(q.size, 0)
        self.assertIsNone(q.pop())
        self.assertIsNone(q.peek())

    def test_push_and_pop(self):
        q = PriorityRequestQueue()
        req = RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="r1")
        q.push(req)
        self.assertEqual(q.size, 1)
        self.assertFalse(q.is_empty)

        result = q.pop()
        self.assertEqual(result.request_id, "r1")
        self.assertTrue(q.is_empty)

    def test_priority_ordering(self):
        q = PriorityRequestQueue()
        # Push in reverse priority order
        q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="data"))
        q.push(RateLimitedRequest(priority=RequestPriority.MARKET_ORDER, request_id="market"))
        q.push(RateLimitedRequest(priority=RequestPriority.LIMIT_ORDER, request_id="limit"))

        self.assertEqual(q.pop().request_id, "market")
        self.assertEqual(q.pop().request_id, "limit")
        self.assertEqual(q.pop().request_id, "data")

    def test_fifo_within_same_priority(self):
        q = PriorityRequestQueue()
        q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="first"))
        q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="second"))
        q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="third"))

        self.assertEqual(q.pop().request_id, "first")
        self.assertEqual(q.pop().request_id, "second")
        self.assertEqual(q.pop().request_id, "third")

    def test_peek_does_not_remove(self):
        q = PriorityRequestQueue()
        q.push(RateLimitedRequest(priority=RequestPriority.MARKET_ORDER, request_id="peek_me"))
        self.assertEqual(q.peek().request_id, "peek_me")
        self.assertEqual(q.size, 1)

    def test_clear(self):
        q = PriorityRequestQueue()
        for i in range(5):
            q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id=f"r{i}"))
        self.assertEqual(q.size, 5)
        q.clear()
        self.assertTrue(q.is_empty)

    def test_mixed_priorities_interleaved(self):
        q = PriorityRequestQueue()
        q.push(RateLimitedRequest(priority=RequestPriority.ACCOUNT_DATA, request_id="acct1"))
        q.push(RateLimitedRequest(priority=RequestPriority.MARKET_ORDER, request_id="mkt1"))
        q.push(RateLimitedRequest(priority=RequestPriority.DATA_REQUEST, request_id="data1"))
        q.push(RateLimitedRequest(priority=RequestPriority.MARKET_ORDER, request_id="mkt2"))
        q.push(RateLimitedRequest(priority=RequestPriority.LIMIT_ORDER, request_id="lmt1"))

        order = [q.pop().request_id for _ in range(5)]
        self.assertEqual(order, ["mkt1", "mkt2", "lmt1", "acct1", "data1"])


if __name__ == "__main__":
    unittest.main()
