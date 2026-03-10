"""
Tests for Agent Gateway Service.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_gateway.main import (
    ChatRequest,
    _gather_chat_context,
    _row_to_event,
    _serialize_row,
    app,
)

_MODULE = "services.agent_gateway.main"


class FakeRecord(dict):
    """Mimics asyncpg.Record for testing."""

    def __init__(self, data):
        super().__init__(data)


class TestSerializeRow:
    """Tests for _serialize_row."""

    def test_converts_datetime(self):
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        row = FakeRecord({"created_at": dt})
        result = _serialize_row(row)
        assert result["created_at"] == dt.isoformat()

    def test_converts_uuid(self):
        uid = uuid.uuid4()
        row = FakeRecord({"id": uid})
        result = _serialize_row(row)
        assert result["id"] == str(uid)

    def test_converts_decimal(self):
        row = FakeRecord({"score": Decimal("0.8542")})
        result = _serialize_row(row)
        assert result["score"] == pytest.approx(0.8542)

    def test_preserves_strings(self):
        row = FakeRecord({"tier": "high", "reasoning": "good signal"})
        result = _serialize_row(row)
        assert result["tier"] == "high"
        assert result["reasoning"] == "good signal"

    def test_preserves_none(self):
        row = FakeRecord({"signal_id": None})
        result = _serialize_row(row)
        assert result["signal_id"] is None


class TestRowToEvent:
    """Tests for _row_to_event."""

    def test_signal_event_type(self):
        row = {
            "id": str(uuid.uuid4()),
            "signal_id": str(uuid.uuid4()),
            "reasoning": None,
            "tool_calls": None,
            "agent_name": "signal-generator",
            "decision_type": None,
            "score": 0.85,
            "tier": "high",
            "model_used": "gpt-4",
            "latency_ms": 150,
            "tokens_used": 500,
            "success": True,
            "error_message": None,
            "created_at": "2026-01-15T10:30:00+00:00",
        }
        event = _row_to_event(row)
        assert event["event_type"] == "signal"

    def test_reasoning_event_type(self):
        row = {
            "id": str(uuid.uuid4()),
            "signal_id": None,
            "reasoning": "Market analysis shows bullish trend",
            "tool_calls": None,
            "agent_name": "strategy-proposer",
            "decision_type": None,
            "score": None,
            "tier": None,
            "model_used": "claude-3",
            "latency_ms": 200,
            "tokens_used": 800,
            "success": True,
            "error_message": None,
            "created_at": "2026-01-15T10:30:00+00:00",
        }
        event = _row_to_event(row)
        # signal_id is None, tool_calls is None, reasoning exists => reasoning
        # But the priority chain: reasoning checked first, then tool_call, then signal
        # Actually in code: reasoning is checked, then tool_call overwrites, then signal overwrites
        # With reasoning=set, tool_calls=None, signal_id=None => "reasoning"
        assert event["event_type"] == "reasoning"

    def test_tool_call_event_type(self):
        row = {
            "id": str(uuid.uuid4()),
            "signal_id": None,
            "reasoning": "Calling market data tool",
            "tool_calls": [{"name": "get_candles", "args": {}}],
            "agent_name": "signal-generator",
            "decision_type": None,
            "score": None,
            "tier": None,
            "model_used": "gpt-4",
            "latency_ms": 300,
            "tokens_used": 600,
            "success": True,
            "error_message": None,
            "created_at": "2026-01-15T10:30:00+00:00",
        }
        event = _row_to_event(row)
        # tool_calls is truthy and overwrites reasoning, signal_id is None
        assert event["event_type"] == "tool_call"

    def test_decision_event_type_default(self):
        row = {
            "id": str(uuid.uuid4()),
            "signal_id": None,
            "reasoning": None,
            "tool_calls": None,
            "agent_name": "scorer",
            "decision_type": "score_update",
            "score": 0.75,
            "tier": "medium",
            "model_used": None,
            "latency_ms": 50,
            "tokens_used": None,
            "success": True,
            "error_message": None,
            "created_at": "2026-01-15T10:30:00+00:00",
        }
        event = _row_to_event(row)
        assert event["event_type"] == "decision"

    def test_event_includes_all_fields(self):
        row = {
            "id": "abc-123",
            "signal_id": "sig-456",
            "reasoning": "test reasoning",
            "tool_calls": [{"name": "test"}],
            "agent_name": "test-agent",
            "decision_type": "test-type",
            "score": 0.9,
            "tier": "high",
            "model_used": "gpt-4",
            "latency_ms": 100,
            "tokens_used": 200,
            "success": True,
            "error_message": None,
            "created_at": "2026-01-15T10:30:00+00:00",
        }
        event = _row_to_event(row)
        assert event["id"] == "abc-123"
        assert event["agent_name"] == "test-agent"
        assert event["score"] == 0.9


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy(self):
        from httpx import ASGITransport, AsyncClient

        # Mock the database pool and redis
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch(f"{_MODULE}._db_pool", mock_pool), patch(
            f"{_MODULE}._redis", mock_redis
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"

    @pytest.mark.asyncio
    async def test_health_returns_degraded_on_db_error(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch(f"{_MODULE}._db_pool", mock_pool), patch(
            f"{_MODULE}._redis", mock_redis
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"


class TestRecentEventsEndpoint:
    """Tests for the /events/recent endpoint."""

    @pytest.mark.asyncio
    async def test_recent_events_returns_list(self):
        from httpx import ASGITransport, AsyncClient

        test_id = uuid.uuid4()
        mock_rows = [
            FakeRecord(
                {
                    "id": test_id,
                    "signal_id": None,
                    "score": Decimal("0.85"),
                    "tier": "high",
                    "reasoning": "Strong bullish signal",
                    "tool_calls": None,
                    "model_used": "gpt-4",
                    "latency_ms": 150,
                    "tokens_used": 500,
                    "created_at": datetime(2026, 1, 15, tzinfo=timezone.utc),
                    "agent_name": "signal-generator",
                    "decision_type": "signal_analysis",
                    "input_context": None,
                    "output": None,
                    "success": True,
                    "error_message": None,
                    "parent_decision_id": None,
                }
            )
        ]

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        mock_redis = AsyncMock()

        with patch(f"{_MODULE}._db_pool", mock_pool), patch(
            f"{_MODULE}._redis", mock_redis
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/events/recent?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["tier"] == "high"

    @pytest.mark.asyncio
    async def test_recent_events_with_agent_filter(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        mock_redis = AsyncMock()

        with patch(f"{_MODULE}._db_pool", mock_pool), patch(
            f"{_MODULE}._redis", mock_redis
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get(
                    "/events/recent?agent_name=signal-generator&limit=5"
                )

        assert response.status_code == 200
        # Verify the query was called with agent_name filter
        mock_conn.fetch.assert_called_once()
        call_args = mock_conn.fetch.call_args
        assert "agent_name" in call_args[0][0]
        assert call_args[0][1] == "signal-generator"

    @pytest.mark.asyncio
    async def test_recent_events_empty(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        mock_redis = AsyncMock()

        with patch(f"{_MODULE}._db_pool", mock_pool), patch(
            f"{_MODULE}._redis", mock_redis
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/events/recent")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["events"] == []


class TestStreamEndpoint:
    """Tests for the /events/stream SSE endpoint."""

    @pytest.mark.asyncio
    async def test_stream_endpoint_exists(self):
        """Verify the stream endpoint is registered."""
        routes = [route.path for route in app.routes]
        assert "/events/stream" in routes

    @pytest.mark.asyncio
    async def test_stream_returns_event_source_response(self):
        from httpx import ASGITransport, AsyncClient

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            yield {
                "type": "message",
                "data": json.dumps(
                    {
                        "event_type": "signal",
                        "id": str(uuid.uuid4()),
                        "agent_name": "test-agent",
                    }
                ),
            }

        mock_pubsub.listen = mock_listen
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch(f"{_MODULE}._redis", mock_redis):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/events/stream")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestChatRequest:
    """Tests for the ChatRequest model."""

    def test_valid_request(self):
        req = ChatRequest(question="What signals are hot?")
        assert req.question == "What signals are hot?"
        assert req.context_window == 50

    def test_custom_context_window(self):
        req = ChatRequest(question="test", context_window=100)
        assert req.context_window == 100

    def test_empty_question_rejected(self):
        with pytest.raises(Exception):
            ChatRequest(question="")

    def test_context_window_bounds(self):
        with pytest.raises(Exception):
            ChatRequest(question="test", context_window=0)
        with pytest.raises(Exception):
            ChatRequest(question="test", context_window=201)


class TestChatEndpoint:
    """Tests for the /chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_exists(self):
        """Verify the chat endpoint is registered."""
        routes = [route.path for route in app.routes]
        assert "/chat" in routes

    @pytest.mark.asyncio
    async def test_chat_returns_503_without_api_key(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_redis = AsyncMock()

        with (
            patch(f"{_MODULE}._db_pool", mock_pool),
            patch(f"{_MODULE}._redis", mock_redis),
            patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=False),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/chat",
                    json={"question": "What is hot?"},
                )

        assert response.status_code == 503
        data = response.json()
        assert "not configured" in data["error"]

    @pytest.mark.asyncio
    async def test_chat_rejects_empty_question(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_redis = AsyncMock()

        with (
            patch(f"{_MODULE}._db_pool", mock_pool),
            patch(f"{_MODULE}._redis", mock_redis),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/chat",
                    json={"question": ""},
                )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_streams_sse_response(self):
        from httpx import ASGITransport, AsyncClient

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm
        mock_redis = AsyncMock()

        # Mock httpx.AsyncClient.stream to return a streaming response
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_aiter_lines():
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield "data: [DONE]"

        mock_response.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_http_client = AsyncMock()
        mock_http_client.stream.return_value = mock_stream_cm
        mock_http_client_cm = AsyncMock()
        mock_http_client_cm.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(f"{_MODULE}._db_pool", mock_pool),
            patch(f"{_MODULE}._redis", mock_redis),
            patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False),
            patch(f"{_MODULE}.httpx.AsyncClient", return_value=mock_http_client_cm),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post(
                    "/chat",
                    json={"question": "What signals are trending?"},
                )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestGatherChatContext:
    """Tests for _gather_chat_context."""

    @pytest.mark.asyncio
    async def test_returns_no_activity_when_empty(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        with patch(f"{_MODULE}._db_pool", mock_pool):
            result = await _gather_chat_context(50)

        assert result == "No recent agent activity found."

    @pytest.mark.asyncio
    async def test_formats_context_from_rows(self):
        mock_rows = [
            FakeRecord(
                {
                    "agent_name": "signal-gen",
                    "decision_type": "analysis",
                    "score": Decimal("0.85"),
                    "tier": "HOT",
                    "reasoning": "Strong uptrend detected",
                    "tool_calls": None,
                    "model_used": "gpt-4",
                    "latency_ms": 150,
                    "success": True,
                    "error_message": None,
                    "created_at": datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                }
            )
        ]

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        with patch(f"{_MODULE}._db_pool", mock_pool):
            result = await _gather_chat_context(50)

        assert "signal-gen" in result
        assert "HOT" in result
        assert "0.85" in result
        assert "Strong uptrend detected" in result
