"""Tests for the dead letter queue."""

import json
import time
from unittest.mock import MagicMock

import pytest

from services.shared.dead_letter_queue import (
    DLQ_KEY,
    DLQ_PROCESSING_KEY,
    DeadLetterQueue,
)
from services.shared.pipeline_metrics import PipelineMetrics


class TestDeadLetterQueue:
    @pytest.fixture
    def redis_mock(self):
        return MagicMock()

    @pytest.fixture
    def dlq(self, redis_mock):
        return DeadLetterQueue(redis_mock, max_retries=3, base_delay=10.0)

    def test_enqueue(self, dlq, redis_mock):
        dlq_id = dlq.enqueue(
            signal={"direction": "BUY", "instrument": "BTC/USD"},
            subscriber_id="sub-1",
            channel="telegram",
            endpoint="12345",
            error="timeout",
        )
        assert dlq_id.startswith("dlq:sub-1:")
        redis_mock.lpush.assert_called_once()
        call_args = redis_mock.lpush.call_args
        assert call_args[0][0] == DLQ_KEY
        entry = json.loads(call_args[0][1])
        assert entry["subscriber_id"] == "sub-1"
        assert entry["channel"] == "telegram"
        assert entry["error"] == "timeout"
        assert entry["retry_count"] == 0

    def test_dequeue_batch_empty(self, dlq, redis_mock):
        redis_mock.rpop.return_value = None
        items = dlq.dequeue_batch(10)
        assert items == []

    def test_dequeue_batch_ready_items(self, dlq, redis_mock):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {"direction": "BUY"},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "error": "timeout",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": time.time() - 100,
            "next_retry_at": time.time() - 10,  # Ready
        }
        redis_mock.rpop.side_effect = [json.dumps(entry), None]
        items = dlq.dequeue_batch(10)
        assert len(items) == 1
        assert items[0]["dlq_id"] == "dlq:sub-1:123"
        redis_mock.hset.assert_called_once()

    def test_dequeue_batch_not_ready(self, dlq, redis_mock):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "error": "timeout",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": time.time(),
            "next_retry_at": time.time() + 1000,  # Not ready
        }
        redis_mock.rpop.side_effect = [json.dumps(entry), None]
        items = dlq.dequeue_batch(10)
        assert len(items) == 0
        # Should be put back
        assert redis_mock.lpush.called

    def test_dequeue_batch_exhausted_retries(self, dlq, redis_mock):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "retry_count": 3,
            "max_retries": 3,
            "next_retry_at": time.time() - 10,
        }
        redis_mock.rpop.side_effect = [json.dumps(entry), None]
        items = dlq.dequeue_batch(10)
        assert len(items) == 0  # Discarded

    def test_ack(self, dlq, redis_mock):
        dlq.ack("dlq:sub-1:123")
        redis_mock.hdel.assert_called_once_with(DLQ_PROCESSING_KEY, "dlq:sub-1:123")

    def test_nack_increments_retry_and_requeues(self, dlq, redis_mock):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "retry_count": 0,
            "max_retries": 3,
        }
        redis_mock.hget.return_value = json.dumps(entry)
        dlq.nack("dlq:sub-1:123")

        redis_mock.hdel.assert_called_once()
        redis_mock.lpush.assert_called_once()
        requeued = json.loads(redis_mock.lpush.call_args[0][1])
        assert requeued["retry_count"] == 1
        assert requeued["next_retry_at"] > time.time()

    def test_nack_discards_exhausted(self, dlq, redis_mock):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "retry_count": 2,
            "max_retries": 3,
        }
        redis_mock.hget.return_value = json.dumps(entry)
        dlq.nack("dlq:sub-1:123")
        redis_mock.hdel.assert_called_once()
        redis_mock.lpush.assert_not_called()  # Discarded, not requeued

    def test_nack_missing_entry(self, dlq, redis_mock):
        redis_mock.hget.return_value = None
        dlq.nack("dlq:nonexistent")  # Should not raise

    def test_size(self, dlq, redis_mock):
        redis_mock.llen.return_value = 5
        assert dlq.size() == 5

    def test_to_dict(self, dlq, redis_mock):
        redis_mock.llen.return_value = 3
        redis_mock.hlen.return_value = 1
        d = dlq.to_dict()
        assert d["pending"] == 3
        assert d["processing"] == 1
        assert d["max_retries"] == 3


class TestDeadLetterQueueMetrics:
    @pytest.fixture
    def redis_mock(self):
        return MagicMock()

    @pytest.fixture
    def metrics(self):
        return PipelineMetrics()

    @pytest.fixture
    def dlq(self, redis_mock, metrics):
        return DeadLetterQueue(redis_mock, max_retries=3, metrics=metrics)

    def test_ack_increments_dlq_retried(self, dlq, redis_mock, metrics):
        dlq.ack("dlq:sub-1:123")
        assert metrics.dlq_retried.value == 1

    def test_nack_exhausted_increments_dlq_exhausted(self, dlq, redis_mock, metrics):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "retry_count": 2,
            "max_retries": 3,
        }
        redis_mock.hget.return_value = json.dumps(entry)
        dlq.nack("dlq:sub-1:123")
        assert metrics.dlq_exhausted.value == 1

    def test_dequeue_exhausted_increments_metric(self, dlq, redis_mock, metrics):
        entry = {
            "dlq_id": "dlq:sub-1:123",
            "signal": {},
            "subscriber_id": "sub-1",
            "channel": "telegram",
            "endpoint": "12345",
            "retry_count": 3,
            "max_retries": 3,
            "next_retry_at": time.time() - 10,
        }
        redis_mock.rpop.side_effect = [json.dumps(entry), None]
        dlq.dequeue_batch(10)
        assert metrics.dlq_exhausted.value == 1
