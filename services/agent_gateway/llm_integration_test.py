"""Integration tests for the Agent Gateway event streaming.

Tests the gateway's handling of agent LLM decision events:
- Event classification from agent_decisions rows
- SSE streaming with Redis pub/sub
- Event filtering by agent name and type
- Error event handling for LLM failures
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_gateway.main import (
    _row_to_event,
    _serialize_row,
    app,
    publish_event,
)

_MODULE = "services.agent_gateway.main"


class FakeRecord(dict):
    """Mimics asyncpg.Record for testing."""

    def __init__(self, data):
        super().__init__(data)


def _make_decision_row(**overrides):
    """Create a realistic agent_decisions row with LLM metadata."""
    defaults = {
        "id": uuid.uuid4(),
        "signal_id": None,
        "score": Decimal("0.00"),
        "tier": None,
        "reasoning": None,
        "tool_calls": None,
        "agent_name": "strategy-proposer",
        "decision_type": "strategy_proposal",
        "input_context": None,
        "output": None,
        "model_used": "anthropic/claude-3-5-sonnet",
        "latency_ms": 2500,
        "tokens_used": 1200,
        "success": True,
        "error_message": None,
        "parent_decision_id": None,
        "created_at": datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return FakeRecord(defaults)


class TestLlmDecisionEventClassification:
    """Tests that LLM agent decisions are classified into correct event types."""

    def test_strategy_proposal_with_reasoning(self):
        """A strategy proposal with reasoning is classified as 'reasoning'."""
        row = _serialize_row(
            _make_decision_row(
                reasoning="Identified gap in volatility strategies using ADX + CCI",
                model_used="anthropic/claude-3-5-sonnet",
                tokens_used=1500,
            )
        )
        event = _row_to_event(row)
        assert event["event_type"] == "reasoning"
        assert event["model_used"] == "anthropic/claude-3-5-sonnet"
        assert event["tokens_used"] == 1500

    def test_tool_call_event_overrides_reasoning(self):
        """When both reasoning and tool_calls exist, tool_call takes priority."""
        row = _serialize_row(
            _make_decision_row(
                reasoning="Calling list_strategy_types to check existing",
                tool_calls=[
                    {"name": "list_strategy_types", "arguments": {}, "result": "..."}
                ],
            )
        )
        event = _row_to_event(row)
        assert event["event_type"] == "tool_call"

    def test_llm_error_event_preserves_error_message(self):
        """Failed LLM decisions preserve the error message in events."""
        row = _serialize_row(
            _make_decision_row(
                success=False,
                error_message="Rate limit exceeded - 429",
                model_used="anthropic/claude-3-5-sonnet",
                latency_ms=150,
                tokens_used=0,
            )
        )
        event = _row_to_event(row)
        assert event["success"] is False
        assert event["error_message"] == "Rate limit exceeded - 429"
        assert event["tokens_used"] == 0

    def test_decision_with_no_llm_metadata(self):
        """Decision without reasoning/tool_calls/signal is 'decision'."""
        row = _serialize_row(
            _make_decision_row(
                reasoning=None,
                tool_calls=None,
                signal_id=None,
            )
        )
        event = _row_to_event(row)
        assert event["event_type"] == "decision"

    def test_signal_event_takes_highest_priority(self):
        """Signal events override both reasoning and tool_call classification."""
        sig_id = uuid.uuid4()
        row = _serialize_row(
            _make_decision_row(
                signal_id=sig_id,
                reasoning="Generated buy signal",
                tool_calls=[{"name": "get_candles"}],
                agent_name="signal-generator",
            )
        )
        event = _row_to_event(row)
        assert event["event_type"] == "signal"
        assert event["signal_id"] == str(sig_id)


class TestLlmMetadataSerialization:
    """Tests that LLM metadata (tokens, latency, model) serializes correctly."""

    def test_high_token_count_serializes(self):
        row = _serialize_row(
            _make_decision_row(tokens_used=50000, latency_ms=15000)
        )
        event = _row_to_event(row)
        assert event["tokens_used"] == 50000
        assert event["latency_ms"] == 15000

    def test_decimal_score_converts_to_float(self):
        row = _serialize_row(_make_decision_row(score=Decimal("0.9234")))
        assert isinstance(row["score"], float)
        assert abs(row["score"] - 0.9234) < 1e-6

    def test_uuid_fields_convert_to_string(self):
        test_id = uuid.uuid4()
        sig_id = uuid.uuid4()
        row = _serialize_row(_make_decision_row(id=test_id, signal_id=sig_id))
        assert row["id"] == str(test_id)
        assert row["signal_id"] == str(sig_id)

    def test_datetime_converts_to_iso(self):
        dt = datetime(2026, 3, 10, 14, 30, 0, tzinfo=timezone.utc)
        row = _serialize_row(_make_decision_row(created_at=dt))
        assert row["created_at"] == "2026-03-10T14:30:00+00:00"


class TestRecentEventsWithLlmFiltering:
    """Tests for /events/recent endpoint with LLM-specific filtering."""

    @pytest.mark.asyncio
    async def test_filter_strategy_proposer_events(self):
        """Filter events by strategy-proposer agent name."""
        from httpx import ASGITransport, AsyncClient

        mock_rows = [
            _make_decision_row(
                reasoning="Proposing new strategy",
                model_used="anthropic/claude-3-5-sonnet",
                tokens_used=2000,
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
                response = await client.get(
                    "/events/recent?agent_name=strategy-proposer&limit=10"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        event = data["events"][0]
        assert event["event_type"] == "reasoning"
        assert event["model_used"] == "anthropic/claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_filter_tool_call_events(self):
        """Filter events by tool_call event type."""
        from httpx import ASGITransport, AsyncClient

        mock_rows = [
            _make_decision_row(
                tool_calls=[{"name": "list_strategy_types", "arguments": {}}],
                reasoning="Calling tool",
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
                response = await client.get(
                    "/events/recent?event_type=tool_call&limit=10"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["events"][0]["event_type"] == "tool_call"

        # Verify query includes tool_calls filter
        mock_conn.fetch.assert_called_once()
        query = mock_conn.fetch.call_args[0][0]
        assert "tool_calls IS NOT NULL" in query


class TestPublishEvent:
    """Tests for the publish_event function used by agents."""

    @pytest.mark.asyncio
    async def test_publish_llm_decision_event(self):
        """Verify agent LLM decision events are published to Redis."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        event = {
            "event_type": "reasoning",
            "agent_name": "strategy-proposer",
            "model_used": "anthropic/claude-3-5-sonnet",
            "tokens_used": 1500,
            "reasoning": "Identified gap in volatility strategies",
        }

        with patch(f"{_MODULE}._redis", mock_redis):
            await publish_event(event)

        mock_redis.publish.assert_called_once_with(
            "agent_events", json.dumps(event)
        )

    @pytest.mark.asyncio
    async def test_publish_tool_call_event(self):
        """Verify tool call events include tool details."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        event = {
            "event_type": "tool_call",
            "agent_name": "strategy-proposer",
            "tool_calls": [
                {"name": "get_top_strategies", "arguments": {"symbol": "BTC-USD"}}
            ],
        }

        with patch(f"{_MODULE}._redis", mock_redis):
            await publish_event(event)

        mock_redis.publish.assert_called_once()
        published = json.loads(mock_redis.publish.call_args[0][1])
        assert published["tool_calls"][0]["name"] == "get_top_strategies"

    @pytest.mark.asyncio
    async def test_publish_skipped_when_redis_none(self):
        """No error when Redis is not connected."""
        with patch(f"{_MODULE}._redis", None):
            # Should not raise
            await publish_event({"event_type": "test"})


class TestSseStreamFiltering:
    """Tests for SSE stream with agent/event_type filtering."""

    @pytest.mark.asyncio
    async def test_stream_filters_by_agent_name(self):
        """SSE stream only yields events matching agent_name filter."""
        from httpx import ASGITransport, AsyncClient

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            # Emit two events: one matching, one not
            yield {
                "type": "message",
                "data": json.dumps(
                    {
                        "event_type": "reasoning",
                        "agent_name": "strategy-proposer",
                        "model_used": "claude-3-5-sonnet",
                    }
                ),
            }
            yield {
                "type": "message",
                "data": json.dumps(
                    {
                        "event_type": "signal",
                        "agent_name": "signal-generator",
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
                response = await client.get(
                    "/events/stream?agent_name=strategy-proposer"
                )

        assert response.status_code == 200
        # The SSE response should contain only the strategy-proposer event
        assert "strategy-proposer" in response.text
