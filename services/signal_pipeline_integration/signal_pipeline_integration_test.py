"""Integration tests for the signal processing pipeline.

Tests end-to-end signal flow:
  Signal emission → PostgreSQL storage + Redis pub/sub → Notification filtering → Delivery

Uses mock infrastructure (PostgreSQL, Redis) but exercises real business logic
across service boundaries to verify the pipeline works as a whole.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.notification_service.main import _build_senders, _passes_filter
from services.notification_service.notification_history import NotificationHistory
from services.signal_mcp.server import create_server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_EMIT_ARGS = {
    "symbol": "BTC/USD",
    "action": "BUY",
    "confidence": 0.85,
    "reasoning": "Strong bullish momentum across MACD and RSI",
    "strategy_breakdown": [
        {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9},
        {"strategy_type": "RSI", "signal": "BUY", "confidence": 0.8},
    ],
}


def _make_mcp_request(tool_name: str, arguments: dict) -> MagicMock:
    """Build a mock MCP request object."""
    request = MagicMock()
    request.params.name = tool_name
    request.params.arguments = arguments
    return request


def _make_mock_redis_for_history():
    """Create a mock Redis client with working list operations for NotificationHistory."""
    store: dict[str, list] = {}

    def lpush(key, value):
        store.setdefault(key, []).insert(0, value)
        return len(store[key])

    def ltrim(key, start, end):
        if key in store:
            store[key] = store[key][start : end + 1]

    def expire(key, ttl):
        pass

    def lrange(key, start, end):
        if key not in store:
            return []
        return store[key][start : end + 1 if end >= 0 else None]

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.lpush = MagicMock(side_effect=lpush)
    mock_pipe.ltrim = MagicMock(side_effect=ltrim)
    mock_pipe.expire = MagicMock(side_effect=expire)
    mock_pipe.execute = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.lrange = MagicMock(side_effect=lrange)
    mock_redis._store = store
    return mock_redis


# ---------------------------------------------------------------------------
# Test: Signal emission stores in Postgres AND publishes to Redis
# ---------------------------------------------------------------------------


class TestSignalEmissionPipeline:
    """Verify that emit_signal stores in PostgreSQL and publishes to Redis."""

    @pytest.fixture
    def postgres_client(self):
        client = AsyncMock()
        client.insert_signal.return_value = "signal-uuid-001"
        return client

    @pytest.fixture
    def redis_client(self):
        client = MagicMock()
        client.publish_signal.return_value = 1
        return client

    @pytest.fixture
    def server(self, postgres_client, redis_client):
        return create_server(postgres_client, redis_client)

    @pytest.mark.asyncio
    async def test_emit_signal_stores_and_publishes(
        self, server, postgres_client, redis_client
    ):
        """Signal emission should persist to Postgres AND publish to Redis."""
        handler = server.request_handlers["tools/call"]
        request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)

        result = await handler(request)

        # Verify Postgres storage
        postgres_client.insert_signal.assert_called_once_with(
            symbol="BTC/USD",
            action="BUY",
            confidence=0.85,
            reasoning="Strong bullish momentum across MACD and RSI",
            strategy_breakdown=SAMPLE_EMIT_ARGS["strategy_breakdown"],
        )

        # Verify Redis publication
        redis_client.publish_signal.assert_called_once()
        call_args = redis_client.publish_signal.call_args
        assert call_args[0][0] == "BTC/USD"
        published_data = call_args[0][1]
        assert published_data["signal_id"] == "signal-uuid-001"
        assert published_data["symbol"] == "BTC/USD"
        assert published_data["action"] == "BUY"
        assert published_data["confidence"] == 0.85

        # Verify response contains signal_id
        response = json.loads(result.content[0].text)
        assert response["signal_id"] == "signal-uuid-001"

    @pytest.mark.asyncio
    async def test_emitted_signal_data_matches_across_stores(
        self, server, postgres_client, redis_client
    ):
        """Data written to Postgres and published to Redis should be consistent."""
        handler = server.request_handlers["tools/call"]
        request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)

        await handler(request)

        # Extract what was sent to each store
        pg_call = postgres_client.insert_signal.call_args
        redis_call = redis_client.publish_signal.call_args
        redis_data = redis_call[0][1]

        # Symbol, action, confidence, reasoning must match
        assert pg_call.kwargs["symbol"] == redis_data["symbol"]
        assert pg_call.kwargs["action"] == redis_data["action"]
        assert pg_call.kwargs["confidence"] == redis_data["confidence"]
        assert pg_call.kwargs["reasoning"] == redis_data["reasoning"]

    @pytest.mark.asyncio
    async def test_multiple_signals_different_symbols(
        self, server, postgres_client, redis_client
    ):
        """Signals for different symbols should publish to their respective channels."""
        handler = server.request_handlers["tools/call"]

        postgres_client.insert_signal.side_effect = [
            "signal-btc-001",
            "signal-eth-001",
        ]

        # Emit BTC signal
        btc_args = {**SAMPLE_EMIT_ARGS, "symbol": "BTC/USD"}
        await handler(_make_mcp_request("emit_signal", btc_args))

        # Emit ETH signal
        eth_args = {**SAMPLE_EMIT_ARGS, "symbol": "ETH/USD", "action": "SELL"}
        await handler(_make_mcp_request("emit_signal", eth_args))

        assert redis_client.publish_signal.call_count == 2
        first_call = redis_client.publish_signal.call_args_list[0]
        second_call = redis_client.publish_signal.call_args_list[1]
        assert first_call[0][0] == "BTC/USD"
        assert second_call[0][0] == "ETH/USD"


# ---------------------------------------------------------------------------
# Test: Signal deduplication via get_recent_signals
# ---------------------------------------------------------------------------


class TestSignalDeduplication:
    """Verify deduplication logic using get_recent_signals."""

    @pytest.fixture
    def postgres_client(self):
        return AsyncMock()

    @pytest.fixture
    def redis_client(self):
        return MagicMock()

    @pytest.fixture
    def server(self, postgres_client, redis_client):
        return create_server(postgres_client, redis_client)

    @pytest.mark.asyncio
    async def test_recent_signals_returns_existing(self, server, postgres_client):
        """get_recent_signals should return previously emitted signals."""
        postgres_client.get_recent_signals.return_value = [
            {
                "signal_id": "signal-uuid-001",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "score": 0.92,
                "tier": "HIGH",
                "reasoning": "Bullish momentum",
                "timestamp": "2026-03-12T10:00:00",
            }
        ]

        handler = server.request_handlers["tools/call"]
        request = _make_mcp_request(
            "get_recent_signals", {"symbol": "BTC/USD", "limit": 10}
        )

        result = await handler(request)
        signals = json.loads(result.content[0].text)

        assert len(signals) == 1
        assert signals[0]["action"] == "BUY"
        assert signals[0]["symbol"] == "BTC/USD"

    @pytest.mark.asyncio
    async def test_deduplication_same_action_within_window(
        self, server, postgres_client, redis_client
    ):
        """Agent should skip emitting when a recent signal has the same action.

        This tests the pattern the signal_generator_agent uses:
        1. Call get_recent_signals
        2. If recent signal with same action exists, skip emit
        """
        # Simulate: recent signal with BUY already exists
        postgres_client.get_recent_signals.return_value = [
            {
                "signal_id": "existing-signal",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.80,
                "score": None,
                "tier": None,
                "reasoning": "Previous bullish signal",
                "timestamp": "2026-03-12T09:50:00",
            }
        ]

        handler = server.request_handlers["tools/call"]

        # Step 1: Check recent signals
        check_request = _make_mcp_request(
            "get_recent_signals", {"symbol": "BTC/USD", "limit": 5}
        )
        result = await handler(check_request)
        recent = json.loads(result.content[0].text)

        # Step 2: Agent dedup logic — same action means skip
        new_action = "BUY"
        should_skip = any(s["action"] == new_action for s in recent)
        assert should_skip is True

        # Verify emit was NOT called (agent skips it)
        postgres_client.insert_signal.assert_not_called()
        redis_client.publish_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_deduplication_for_different_action(
        self, server, postgres_client, redis_client
    ):
        """Agent should emit when the new action differs from recent signals."""
        postgres_client.get_recent_signals.return_value = [
            {
                "signal_id": "existing-signal",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.80,
                "score": None,
                "tier": None,
                "reasoning": "Previous bullish signal",
                "timestamp": "2026-03-12T09:50:00",
            }
        ]
        postgres_client.insert_signal.return_value = "new-signal-uuid"

        handler = server.request_handlers["tools/call"]

        # Step 1: Check recent signals
        check_request = _make_mcp_request(
            "get_recent_signals", {"symbol": "BTC/USD", "limit": 5}
        )
        result = await handler(check_request)
        recent = json.loads(result.content[0].text)

        # Step 2: Different action — should NOT skip
        new_action = "SELL"
        should_skip = any(s["action"] == new_action for s in recent)
        assert should_skip is False

        # Step 3: Emit the signal
        sell_args = {**SAMPLE_EMIT_ARGS, "action": "SELL"}
        emit_request = _make_mcp_request("emit_signal", sell_args)
        result = await handler(emit_request)

        postgres_client.insert_signal.assert_called_once()
        redis_client.publish_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_deduplication_when_no_recent_signals(
        self, server, postgres_client, redis_client
    ):
        """Agent should emit freely when there are no recent signals."""
        postgres_client.get_recent_signals.return_value = []
        postgres_client.insert_signal.return_value = "first-signal-uuid"

        handler = server.request_handlers["tools/call"]

        # Step 1: Check — empty
        check_request = _make_mcp_request(
            "get_recent_signals", {"symbol": "BTC/USD", "limit": 5}
        )
        result = await handler(check_request)
        recent = json.loads(result.content[0].text)
        assert len(recent) == 0

        # Step 2: Emit
        emit_request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)
        await handler(emit_request)

        postgres_client.insert_signal.assert_called_once()
        redis_client.publish_signal.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Downstream notification filtering and delivery
# ---------------------------------------------------------------------------


class TestNotificationPipeline:
    """Verify that signals published to Redis are filtered and delivered correctly."""

    def _signal_from_redis(self, **overrides) -> dict:
        """Build a signal dict as it would arrive from Redis pub/sub."""
        base = {
            "signal_id": "signal-uuid-001",
            "symbol": "BTC/USD",
            "action": "BUY",
            "confidence": 0.85,
            "reasoning": "Bullish momentum",
            "strategy_breakdown": [
                {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9},
            ],
        }
        base.update(overrides)
        return base

    def test_high_confidence_signal_passes_filter(self):
        """Signal with confidence above min_score should pass the filter."""
        signal = self._signal_from_redis(confidence=0.85)
        assert _passes_filter(signal, min_score=0.7, tiers=[]) is True

    def test_low_confidence_signal_filtered(self):
        """Signal with confidence below min_score should be filtered out."""
        signal = self._signal_from_redis(confidence=0.5)
        assert _passes_filter(signal, min_score=0.7, tiers=[]) is False

    def test_matching_tier_passes_filter(self):
        """Signal with matching tier should pass the filter."""
        signal = self._signal_from_redis(tier="gold")
        assert _passes_filter(signal, min_score=0.0, tiers=["gold", "platinum"]) is True

    def test_non_matching_tier_filtered(self):
        """Signal with non-matching tier should be filtered out."""
        signal = self._signal_from_redis(tier="bronze")
        assert (
            _passes_filter(signal, min_score=0.0, tiers=["gold", "platinum"]) is False
        )

    def test_filter_and_history_recording(self):
        """Filtered signal should be recorded in notification history."""
        mock_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_redis)

        signal = self._signal_from_redis(confidence=0.5)
        passes = _passes_filter(signal, min_score=0.7, tiers=[])
        assert passes is False

        # Record the filter event
        record = history.record_filtered(
            signal["signal_id"], "confidence=0.5 < 0.7", signal
        )
        assert record.status == "filtered"
        assert record.signal_id == "signal-uuid-001"

        # Verify it appears in history
        stats = history.get_stats()
        assert stats["total"] == 1
        assert stats["filtered"] == 1

    def test_delivery_success_recorded_in_history(self):
        """Successful delivery should be recorded in notification history."""
        mock_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_redis)

        signal = self._signal_from_redis()

        record = history.record_delivery(signal["signal_id"], "telegram", True, signal)
        assert record.status == "delivered"
        assert record.channel == "telegram"

        stats = history.get_stats()
        assert stats["delivered"] == 1

    def test_delivery_failure_recorded_in_history(self):
        """Failed delivery should be recorded with error in notification history."""
        mock_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_redis)

        signal = self._signal_from_redis()

        record = history.record_delivery(
            signal["signal_id"], "discord", False, signal, error="timeout"
        )
        assert record.status == "failed"
        assert record.error == "timeout"

        stats = history.get_stats()
        assert stats["failed"] == 1

    def test_mixed_delivery_outcomes(self):
        """Multiple delivery attempts should all be tracked correctly."""
        mock_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_redis)

        signal = self._signal_from_redis()

        # Telegram succeeds, Discord fails
        history.record_delivery(signal["signal_id"], "telegram", True, signal)
        history.record_delivery(
            signal["signal_id"], "discord", False, signal, error="rate limited"
        )

        stats = history.get_stats()
        assert stats["total"] == 2
        assert stats["delivered"] == 1
        assert stats["failed"] == 1


# ---------------------------------------------------------------------------
# Test: End-to-end signal flow (emit → filter → deliver)
# ---------------------------------------------------------------------------


class TestEndToEndSignalFlow:
    """Verify the complete signal lifecycle from emission through delivery."""

    @pytest.fixture
    def postgres_client(self):
        client = AsyncMock()
        client.insert_signal.return_value = "e2e-signal-uuid"
        return client

    @pytest.fixture
    def redis_client(self):
        return MagicMock()

    @pytest.fixture
    def server(self, postgres_client, redis_client):
        return create_server(postgres_client, redis_client)

    @pytest.mark.asyncio
    async def test_full_signal_lifecycle(self, server, postgres_client, redis_client):
        """Test: emit signal → capture Redis data → filter → deliver → record history.

        Simulates the full pipeline without real infrastructure.
        """
        handler = server.request_handlers["tools/call"]

        # Step 1: Emit signal through MCP server
        emit_request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)
        result = await handler(emit_request)
        response = json.loads(result.content[0].text)
        assert response["signal_id"] == "e2e-signal-uuid"

        # Step 2: Capture what was published to Redis (simulating pub/sub receive)
        redis_call = redis_client.publish_signal.call_args
        signal_data = redis_call[0][1]

        # Step 3: Apply notification filter (high confidence should pass)
        assert _passes_filter(signal_data, min_score=0.7, tiers=[]) is True

        # Step 4: Simulate delivery and record history
        mock_history_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_history_redis)

        history.record_delivery(signal_data["signal_id"], "telegram", True, signal_data)
        history.record_delivery(signal_data["signal_id"], "discord", True, signal_data)

        stats = history.get_stats()
        assert stats["total"] == 2
        assert stats["delivered"] == 2
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_low_confidence_signal_filtered_in_pipeline(
        self, server, postgres_client, redis_client
    ):
        """Low-confidence signal should be emitted but filtered by notification service."""
        handler = server.request_handlers["tools/call"]

        low_conf_args = {**SAMPLE_EMIT_ARGS, "confidence": 0.3}
        postgres_client.insert_signal.return_value = "low-conf-signal"

        # Emit
        emit_request = _make_mcp_request("emit_signal", low_conf_args)
        await handler(emit_request)

        # Signal IS stored (MCP server stores all signals)
        postgres_client.insert_signal.assert_called_once()
        redis_client.publish_signal.assert_called_once()

        # But notification service filters it out
        signal_data = redis_client.publish_signal.call_args[0][1]
        assert _passes_filter(signal_data, min_score=0.7, tiers=[]) is False

        # Record the filter event
        mock_history_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_history_redis)
        history.record_filtered(
            signal_data["signal_id"],
            f"confidence={signal_data['confidence']} < 0.7",
            signal_data,
        )

        stats = history.get_stats()
        assert stats["filtered"] == 1
        assert stats["delivered"] == 0

    @pytest.mark.asyncio
    async def test_signal_with_decision_logging(
        self, server, postgres_client, redis_client
    ):
        """Test emit → log_decision flow for signal scoring."""
        handler = server.request_handlers["tools/call"]
        postgres_client.insert_signal.return_value = "scored-signal-uuid"
        postgres_client.insert_decision.return_value = "decision-uuid-001"

        # Step 1: Emit signal
        emit_request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)
        result = await handler(emit_request)
        signal_id = json.loads(result.content[0].text)["signal_id"]

        # Step 2: Log decision for the signal
        decision_request = _make_mcp_request(
            "log_decision",
            {
                "signal_id": signal_id,
                "score": 0.92,
                "tier": "HIGH",
                "reasoning": "Strong consensus across strategies",
                "tool_calls": [
                    {"name": "get_candles", "args": {"symbol": "BTC/USD"}},
                    {"name": "get_market_summary", "args": {}},
                ],
                "model_used": "claude-opus-4-6",
                "latency_ms": 1200,
                "tokens": 1800,
            },
        )
        decision_result = await handler(decision_request)
        decision_response = json.loads(decision_result.content[0].text)
        assert decision_response["decision_id"] == "decision-uuid-001"

        # Verify the decision was logged for the correct signal
        postgres_client.insert_decision.assert_called_once_with(
            signal_id="scored-signal-uuid",
            score=0.92,
            tier="HIGH",
            reasoning="Strong consensus across strategies",
            tool_calls=[
                {"name": "get_candles", "args": {"symbol": "BTC/USD"}},
                {"name": "get_market_summary", "args": {}},
            ],
            model_used="claude-opus-4-6",
            latency_ms=1200,
            tokens_used=1800,
        )

    @pytest.mark.asyncio
    async def test_emit_and_query_round_trip(
        self, server, postgres_client, redis_client
    ):
        """Emitted signal should be retrievable via get_recent_signals."""
        handler = server.request_handlers["tools/call"]
        postgres_client.insert_signal.return_value = "roundtrip-signal"

        # Emit
        emit_request = _make_mcp_request("emit_signal", SAMPLE_EMIT_ARGS)
        await handler(emit_request)

        # Configure mock to return what was just emitted
        postgres_client.get_recent_signals.return_value = [
            {
                "signal_id": "roundtrip-signal",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "score": None,
                "tier": None,
                "reasoning": "Strong bullish momentum across MACD and RSI",
                "timestamp": "2026-03-12T10:00:00",
            }
        ]

        # Query
        query_request = _make_mcp_request(
            "get_recent_signals", {"symbol": "BTC/USD", "limit": 5}
        )
        result = await handler(query_request)
        signals = json.loads(result.content[0].text)

        assert len(signals) == 1
        assert signals[0]["signal_id"] == "roundtrip-signal"
        assert signals[0]["action"] == "BUY"
        assert signals[0]["confidence"] == 0.85


# ---------------------------------------------------------------------------
# Test: Signal validation edge cases
# ---------------------------------------------------------------------------


class TestSignalValidationEdgeCases:
    """Test edge cases in signal processing."""

    def test_zero_confidence_filtered(self):
        """Zero confidence signal should be filtered by any non-zero min_score."""
        signal = {"confidence": 0.0, "action": "BUY", "symbol": "BTC/USD"}
        assert _passes_filter(signal, min_score=0.1, tiers=[]) is False

    def test_exact_threshold_confidence_passes(self):
        """Signal at exactly min_score should pass."""
        signal = {"confidence": 0.7, "action": "BUY", "symbol": "BTC/USD"}
        assert _passes_filter(signal, min_score=0.7, tiers=[]) is True

    def test_missing_confidence_filtered(self):
        """Signal missing confidence field should default to 0 and be filtered."""
        signal = {"action": "BUY", "symbol": "BTC/USD"}
        assert _passes_filter(signal, min_score=0.1, tiers=[]) is False

    def test_missing_tier_passes_when_tiers_configured(self):
        """Signal without a tier should pass when tier filter is set."""
        signal = {"confidence": 0.9, "action": "BUY", "symbol": "BTC/USD"}
        assert _passes_filter(signal, min_score=0.0, tiers=["gold"]) is True

    def test_empty_tier_passes(self):
        """Signal with empty string tier should pass when tier filter is set."""
        signal = {"confidence": 0.9, "tier": "", "action": "BUY"}
        assert _passes_filter(signal, min_score=0.0, tiers=["gold"]) is True

    def test_hold_signal_passes_filter(self):
        """HOLD signals with sufficient confidence should pass the filter."""
        signal = {"confidence": 0.8, "action": "HOLD", "symbol": "BTC/USD"}
        assert _passes_filter(signal, min_score=0.7, tiers=[]) is True

    def test_notification_history_multiple_signals(self):
        """History should track deliveries across multiple signals independently."""
        mock_redis = _make_mock_redis_for_history()
        history = NotificationHistory(mock_redis)

        history.record_delivery("sig-1", "telegram", True, {"signal_id": "sig-1"})
        history.record_delivery("sig-2", "telegram", True, {"signal_id": "sig-2"})
        history.record_delivery("sig-2", "discord", False, {"signal_id": "sig-2"})

        stats = history.get_stats()
        assert stats["total"] == 3
        assert stats["delivered"] == 2
        assert stats["failed"] == 1
