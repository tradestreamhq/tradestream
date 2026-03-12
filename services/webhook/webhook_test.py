"""Tests for the webhook notification service."""

import json
import time
from unittest import mock

import pytest

from services.webhook.delivery import (
    build_headers,
    compute_signature,
    deliver,
    verify_signature,
)
from services.webhook.models import (
    DeliveryRecord,
    DeliveryStatus,
    EventType,
    WebhookEvent,
    WebhookRegistration,
)
from services.webhook.service import WebhookService


SAMPLE_TRADE_PAYLOAD = {
    "trade_id": "t-001",
    "symbol": "BTC/USD",
    "side": "BUY",
    "quantity": 0.5,
    "price": 65000.0,
    "executed_at": "2026-03-12T10:00:00Z",
}


# ── Model tests ──────────────────────────────────────────────────────


class TestWebhookRegistration:
    def test_create(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="s3cret",
            event_types=["trade.executed"],
            description="Test hook",
        )
        assert reg.url == "https://example.com/hook"
        assert reg.secret == "s3cret"
        assert reg.active is True
        assert len(reg.webhook_id) == 16

    def test_accepts_matching_event(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="",
            event_types=["trade.executed", "position.opened"],
        )
        assert reg.accepts_event("trade.executed") is True
        assert reg.accepts_event("position.opened") is True

    def test_rejects_non_matching_event(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="",
            event_types=["trade.executed"],
        )
        assert reg.accepts_event("alert.triggered") is False

    def test_accepts_all_when_no_filter(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="",
            event_types=[],
        )
        assert reg.accepts_event("trade.executed") is True
        assert reg.accepts_event("alert.triggered") is True

    def test_rejects_when_inactive(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="",
            event_types=[],
        )
        reg.active = False
        assert reg.accepts_event("trade.executed") is False

    def test_to_dict(self):
        reg = WebhookRegistration.create(
            url="https://example.com/hook",
            secret="s3cret",
            event_types=["trade.executed"],
        )
        d = reg.to_dict()
        assert d["url"] == "https://example.com/hook"
        assert d["event_types"] == ["trade.executed"]


class TestWebhookEvent:
    def test_create(self):
        event = WebhookEvent.create("trade.executed", SAMPLE_TRADE_PAYLOAD)
        assert event.event_type == "trade.executed"
        assert event.payload["symbol"] == "BTC/USD"
        assert len(event.event_id) == 16


class TestDeliveryRecord:
    def test_create_pending(self):
        record = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        assert record.status == "pending"
        assert record.attempt == 0
        assert record.max_attempts == 3

    def test_mark_delivered(self):
        record = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        record.mark_delivered(200)
        assert record.status == "delivered"
        assert record.status_code == 200
        assert record.completed_at > 0

    def test_mark_failed(self):
        record = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        record.mark_failed("timeout", 500)
        assert record.status == "failed"
        assert record.error == "timeout"
        assert record.status_code == 500


# ── Signature tests ──────────────────────────────────────────────────


class TestSignature:
    def test_compute_deterministic(self):
        sig1 = compute_signature("secret", "12345", '{"key":"value"}')
        sig2 = compute_signature("secret", "12345", '{"key":"value"}')
        assert sig1 == sig2
        assert len(sig1) == 64

    def test_compute_changes_with_timestamp(self):
        sig1 = compute_signature("secret", "12345", '{"key":"value"}')
        sig2 = compute_signature("secret", "12346", '{"key":"value"}')
        assert sig1 != sig2

    def test_compute_changes_with_secret(self):
        sig1 = compute_signature("secret1", "12345", '{"key":"value"}')
        sig2 = compute_signature("secret2", "12345", '{"key":"value"}')
        assert sig1 != sig2

    def test_verify_valid(self):
        sig = compute_signature("secret", "12345", '{"key":"value"}')
        assert verify_signature("secret", "12345", '{"key":"value"}', sig) is True

    def test_verify_invalid(self):
        assert verify_signature("secret", "12345", '{"key":"value"}', "bad") is False

    def test_verify_wrong_secret(self):
        sig = compute_signature("secret", "12345", '{"key":"value"}')
        assert verify_signature("wrong", "12345", '{"key":"value"}', sig) is False


class TestBuildHeaders:
    def test_headers_with_secret(self):
        headers = build_headers("my-secret", '{"data":1}')
        assert headers["Content-Type"] == "application/json"
        assert "X-TradeStream-Timestamp" in headers
        assert "X-TradeStream-Signature" in headers
        assert len(headers["X-TradeStream-Signature"]) == 64

    def test_headers_without_secret(self):
        headers = build_headers("", '{"data":1}')
        assert "X-TradeStream-Signature" not in headers
        assert "X-TradeStream-Timestamp" in headers


# ── Delivery tests ───────────────────────────────────────────────────


class TestDeliver:
    def _make_reg(self, url="https://example.com/hook", secret="secret"):
        return WebhookRegistration.create(
            url=url, secret=secret, event_types=["trade.executed"]
        )

    def _make_event(self):
        return WebhookEvent.create("trade.executed", SAMPLE_TRADE_PAYLOAD)

    @mock.patch("services.webhook.delivery.requests.post")
    def test_success_first_attempt(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        record = deliver(self._make_reg(), self._make_event())
        assert record.status == "delivered"
        assert record.attempt == 1
        assert mock_post.call_count == 1

    @mock.patch("services.webhook.delivery.requests.post")
    def test_client_error_no_retry(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Bad Request")
        record = deliver(self._make_reg(), self._make_event())
        assert record.status == "failed"
        assert record.attempt == 1
        assert mock_post.call_count == 1

    @mock.patch("services.webhook.delivery.time.sleep")
    @mock.patch("services.webhook.delivery.requests.post")
    def test_server_error_retries(self, mock_post, mock_sleep):
        mock_post.return_value = mock.Mock(
            status_code=500, text="Internal Server Error"
        )
        record = deliver(self._make_reg(), self._make_event(), max_attempts=3)
        assert record.status == "failed"
        assert record.attempt == 3
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

    @mock.patch("services.webhook.delivery.time.sleep")
    @mock.patch("services.webhook.delivery.requests.post")
    def test_retry_then_success(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            mock.Mock(status_code=500, text="error"),
            mock.Mock(status_code=200),
        ]
        record = deliver(self._make_reg(), self._make_event(), max_attempts=3)
        assert record.status == "delivered"
        assert record.attempt == 2

    @mock.patch("services.webhook.delivery.time.sleep")
    @mock.patch("services.webhook.delivery.requests.post")
    def test_network_error_retries(self, mock_post, mock_sleep):
        import requests as req

        mock_post.side_effect = req.RequestException("connection refused")
        record = deliver(self._make_reg(), self._make_event(), max_attempts=3)
        assert record.status == "failed"
        assert record.attempt == 3
        assert "connection refused" in record.error

    @mock.patch("services.webhook.delivery.time.sleep")
    @mock.patch("services.webhook.delivery.requests.post")
    def test_exponential_backoff(self, mock_post, mock_sleep):
        mock_post.return_value = mock.Mock(status_code=500, text="error")
        deliver(self._make_reg(), self._make_event(), max_attempts=3)
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [2, 4]  # 2^1, 2^2

    @mock.patch("services.webhook.delivery.requests.post")
    def test_sends_hmac_headers(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        deliver(self._make_reg(secret="test-secret"), self._make_event())
        headers = mock_post.call_args[1]["headers"]
        assert "X-TradeStream-Signature" in headers
        assert "X-TradeStream-Timestamp" in headers

    @mock.patch("services.webhook.delivery.requests.post")
    def test_payload_envelope(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        event = self._make_event()
        deliver(self._make_reg(), event)
        body = json.loads(mock_post.call_args[1]["data"])
        assert body["event_id"] == event.event_id
        assert body["event_type"] == "trade.executed"
        assert body["data"]["symbol"] == "BTC/USD"


# ── Service tests ────────────────────────────────────────────────────


class TestWebhookService:
    def _make_mock_redis(self):
        hash_store = {}
        list_store = {}

        def hset(key, field, value):
            hash_store.setdefault(key, {})[field] = value

        def hget(key, field):
            return hash_store.get(key, {}).get(field)

        def hdel(key, field):
            if key in hash_store and field in hash_store[key]:
                del hash_store[key][field]
                return 1
            return 0

        def hgetall(key):
            return hash_store.get(key, {})

        def lpush(key, value):
            list_store.setdefault(key, []).insert(0, value)

        def ltrim(key, start, end):
            if key in list_store:
                list_store[key] = list_store[key][start : end + 1]

        def expire(key, ttl):
            pass

        def lrange(key, start, end):
            if key not in list_store:
                return []
            return list_store[key][start : end + 1 if end >= 0 else None]

        mock_redis = mock.MagicMock()
        mock_redis.hset = mock.MagicMock(side_effect=hset)
        mock_redis.hget = mock.MagicMock(side_effect=hget)
        mock_redis.hdel = mock.MagicMock(side_effect=hdel)
        mock_redis.hgetall = mock.MagicMock(side_effect=hgetall)

        mock_pipe = mock.MagicMock()
        mock_pipe.lpush = mock.MagicMock(side_effect=lpush)
        mock_pipe.ltrim = mock.MagicMock(side_effect=ltrim)
        mock_pipe.expire = mock.MagicMock(side_effect=expire)
        mock_pipe.execute = mock.MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.lrange = mock.MagicMock(side_effect=lrange)
        return mock_redis

    def test_register(self):
        svc = WebhookService(self._make_mock_redis())
        reg = svc.register(
            "https://example.com/hook",
            "secret",
            ["trade.executed"],
            "My hook",
        )
        assert reg.url == "https://example.com/hook"
        assert reg.event_types == ["trade.executed"]

    def test_register_invalid_event_type(self):
        svc = WebhookService(self._make_mock_redis())
        with pytest.raises(ValueError, match="Unknown event type"):
            svc.register("https://example.com", "s", ["bad.event"])

    def test_list_registrations(self):
        svc = WebhookService(self._make_mock_redis())
        svc.register("https://a.com/hook", "s1", ["trade.executed"])
        svc.register("https://b.com/hook", "s2", ["position.opened"])
        regs = svc.list_registrations()
        assert len(regs) == 2

    def test_get_registration(self):
        svc = WebhookService(self._make_mock_redis())
        reg = svc.register("https://a.com/hook", "s1", ["trade.executed"])
        found = svc.get_registration(reg.webhook_id)
        assert found is not None
        assert found.url == "https://a.com/hook"

    def test_get_registration_not_found(self):
        svc = WebhookService(self._make_mock_redis())
        assert svc.get_registration("nonexistent") is None

    def test_unregister(self):
        svc = WebhookService(self._make_mock_redis())
        reg = svc.register("https://a.com/hook", "s1", [])
        assert svc.unregister(reg.webhook_id) is True
        assert svc.get_registration(reg.webhook_id) is None

    def test_unregister_nonexistent(self):
        svc = WebhookService(self._make_mock_redis())
        assert svc.unregister("nonexistent") is False

    @mock.patch("services.webhook.service.deliver")
    def test_dispatch_to_matching_webhooks(self, mock_deliver):
        mock_deliver.return_value = DeliveryRecord.create(
            "wh-1", "ev-1", "trade.executed"
        )
        svc = WebhookService(self._make_mock_redis())
        svc.register("https://a.com/hook", "s1", ["trade.executed"])
        svc.register("https://b.com/hook", "s2", ["position.opened"])

        records = svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)
        assert len(records) == 1
        assert mock_deliver.call_count == 1

    @mock.patch("services.webhook.service.deliver")
    def test_dispatch_to_all_when_no_filter(self, mock_deliver):
        mock_deliver.return_value = DeliveryRecord.create(
            "wh-1", "ev-1", "trade.executed"
        )
        svc = WebhookService(self._make_mock_redis())
        svc.register("https://a.com/hook", "s1", [])
        svc.register("https://b.com/hook", "s2", [])

        records = svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)
        assert len(records) == 2

    @mock.patch("services.webhook.service.deliver")
    def test_dispatch_stores_delivery_records(self, mock_deliver):
        record = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        record.mark_delivered(200)
        mock_deliver.return_value = record

        redis = self._make_mock_redis()
        svc = WebhookService(redis)
        svc.register("https://a.com/hook", "s1", [])
        svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)

        deliveries = svc.get_deliveries()
        assert len(deliveries) == 1
        assert deliveries[0]["status"] == "delivered"

    @mock.patch("services.webhook.service.deliver")
    def test_delivery_stats(self, mock_deliver):
        redis = self._make_mock_redis()
        svc = WebhookService(redis)
        svc.register("https://a.com/hook", "s1", [])

        delivered = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        delivered.mark_delivered(200)
        failed = DeliveryRecord.create("wh-1", "ev-2", "trade.executed")
        failed.mark_failed("timeout")

        mock_deliver.side_effect = [delivered, failed]
        svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)
        svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)

        stats = svc.get_delivery_stats()
        assert stats["total"] == 2
        assert stats["delivered"] == 1
        assert stats["failed"] == 1

    @mock.patch("services.webhook.service.deliver")
    def test_get_deliveries_filtered_by_status(self, mock_deliver):
        redis = self._make_mock_redis()
        svc = WebhookService(redis)
        svc.register("https://a.com/hook", "s1", [])

        delivered = DeliveryRecord.create("wh-1", "ev-1", "trade.executed")
        delivered.mark_delivered(200)
        failed = DeliveryRecord.create("wh-1", "ev-2", "trade.executed")
        failed.mark_failed("timeout")

        mock_deliver.side_effect = [delivered, failed]
        svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)
        svc.dispatch("trade.executed", SAMPLE_TRADE_PAYLOAD)

        failed_only = svc.get_deliveries(status="failed")
        assert len(failed_only) == 1
        assert failed_only[0]["status"] == "failed"
