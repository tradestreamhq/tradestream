"""Tests for webhook delivery module."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.webhook_api.delivery import (
    VALID_EVENT_TYPES,
    build_delivery_headers,
    deliver_webhook,
    deliver_with_retries,
    sign_payload,
)


class TestSignPayload:
    def test_sign_payload_deterministic(self):
        payload = b'{"key": "value"}'
        secret = "test-secret"
        sig1 = sign_payload(payload, secret)
        sig2 = sign_payload(payload, secret)
        assert sig1 == sig2

    def test_sign_payload_matches_hmac(self):
        payload = b'{"event": "trade.executed"}'
        secret = "my-secret-key"
        expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        assert sign_payload(payload, secret) == expected

    def test_different_secrets_produce_different_signatures(self):
        payload = b"same payload"
        sig1 = sign_payload(payload, "secret-1")
        sig2 = sign_payload(payload, "secret-2")
        assert sig1 != sig2


class TestBuildDeliveryHeaders:
    def test_headers_contain_required_fields(self):
        headers = build_delivery_headers("abc123", "trade.executed", "delivery-id-1")
        assert headers["Content-Type"] == "application/json"
        assert headers["X-TradeStream-Signature"] == "sha256=abc123"
        assert headers["X-TradeStream-Event"] == "trade.executed"
        assert headers["X-TradeStream-Delivery"] == "delivery-id-1"


class TestValidEventTypes:
    def test_expected_event_types(self):
        assert "trade.executed" in VALID_EVENT_TYPES
        assert "alert.triggered" in VALID_EVENT_TYPES
        assert "strategy.signal" in VALID_EVENT_TYPES
        assert "backtest.completed" in VALID_EVENT_TYPES
        assert len(VALID_EVENT_TYPES) == 4


class TestDeliverWebhook:
    @pytest.mark.asyncio
    async def test_successful_delivery(self):
        mock_response = httpx.Response(200, text="OK")

        with patch("services.webhook_api.delivery.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await deliver_webhook(
                url="https://example.com/hook",
                secret="test-secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_failed_delivery_http_error(self):
        mock_response = httpx.Response(500, text="Internal Server Error")

        with patch("services.webhook_api.delivery.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await deliver_webhook(
                url="https://example.com/hook",
                secret="test-secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert result["success"] is False
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_timeout_delivery(self):
        with patch("services.webhook_api.delivery.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.side_effect = httpx.TimeoutException("timed out")
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await deliver_webhook(
                url="https://example.com/hook",
                secret="test-secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert result["success"] is False
        assert result["error"] == "Request timed out"

    @pytest.mark.asyncio
    async def test_connection_error(self):
        with patch("services.webhook_api.delivery.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.side_effect = httpx.ConnectError("connection refused")
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await deliver_webhook(
                url="https://example.com/hook",
                secret="test-secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert result["success"] is False
        assert "connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_signature_is_sent_in_headers(self):
        mock_response = httpx.Response(200, text="OK")

        with patch("services.webhook_api.delivery.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            await deliver_webhook(
                url="https://example.com/hook",
                secret="my-secret",
                event_type="trade.executed",
                payload={"data": "test"},
            )

            call_kwargs = instance.post.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert "X-TradeStream-Signature" in headers
            assert headers["X-TradeStream-Signature"].startswith("sha256=")


class TestDeliverWithRetries:
    def _make_pool(self):
        pool = AsyncMock()
        conn = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx
        return pool, conn

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        pool, conn = self._make_pool()
        success_result = {
            "success": True,
            "status_code": 200,
            "response_body": "OK",
            "error": None,
        }

        with patch(
            "services.webhook_api.delivery.deliver_webhook",
            return_value=success_result,
        ):
            delivery_id = await deliver_with_retries(
                db_pool=pool,
                webhook_id="webhook-1",
                url="https://example.com/hook",
                secret="secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert delivery_id is not None
        # INSERT + UPDATE(success) = at least 2 execute calls
        assert conn.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        pool, conn = self._make_pool()
        fail_result = {
            "success": False,
            "status_code": 500,
            "response_body": "error",
            "error": "HTTP 500",
        }
        success_result = {
            "success": True,
            "status_code": 200,
            "response_body": "OK",
            "error": None,
        }

        with patch(
            "services.webhook_api.delivery.deliver_webhook",
            side_effect=[fail_result, success_result],
        ):
            delivery_id = await deliver_with_retries(
                db_pool=pool,
                webhook_id="webhook-1",
                url="https://example.com/hook",
                secret="secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert delivery_id is not None

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        pool, conn = self._make_pool()
        fail_result = {
            "success": False,
            "status_code": 500,
            "response_body": "error",
            "error": "HTTP 500",
        }

        with patch(
            "services.webhook_api.delivery.deliver_webhook",
            return_value=fail_result,
        ):
            delivery_id = await deliver_with_retries(
                db_pool=pool,
                webhook_id="webhook-1",
                url="https://example.com/hook",
                secret="secret",
                event_type="trade.executed",
                payload={"trade_id": "123"},
            )

        assert delivery_id is not None
        # Check the final status update set status='failed'
        last_execute_call = conn.execute.call_args_list[-1]
        assert "failed" in last_execute_call.args[0]
