"""
Tests for the signal replay engine.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.signal_mcp.audit_recorder import AuditRecorder
from services.signal_mcp.signal_replayer import (
    ReplayResult,
    ReplaySummary,
    SignalReplayer,
)


class TestReplayResult:
    """Test ReplayResult serialization."""

    def test_to_dict_match(self):
        event = {
            "id": "event-1",
            "action": "BUY",
            "confidence": 0.85,
            "symbol": "BTC/USD",
            "created_at": "2026-03-12T10:00:00",
        }
        result = ReplayResult(
            original_event=event,
            replay_event_id="replay-1",
            replay_action="BUY",
            replay_confidence=0.85,
            match=True,
        )

        d = result.to_dict()
        assert d["match"] is True
        assert d["original_action"] == "BUY"
        assert d["replay_action"] == "BUY"
        assert d["symbol"] == "BTC/USD"

    def test_to_dict_mismatch(self):
        event = {
            "id": "event-1",
            "action": "BUY",
            "confidence": 0.85,
            "symbol": "BTC/USD",
            "created_at": "2026-03-12T10:00:00",
        }
        result = ReplayResult(
            original_event=event,
            replay_event_id="replay-1",
            replay_action="SELL",
            replay_confidence=0.6,
            match=False,
        )

        d = result.to_dict()
        assert d["match"] is False
        assert d["original_action"] == "BUY"
        assert d["replay_action"] == "SELL"


class TestReplaySummary:
    """Test ReplaySummary serialization."""

    def test_to_dict_empty(self):
        summary = ReplaySummary(
            replay_group_id="group-1",
            results=[],
            start_time="2026-03-12T00:00:00",
            end_time="2026-03-12T12:00:00",
        )

        d = summary.to_dict()
        assert d["total_events"] == 0
        assert d["matches"] == 0
        assert d["mismatches"] == 0
        assert d["match_rate"] == 0.0

    def test_to_dict_with_results(self):
        event1 = {"id": "e1", "action": "BUY", "confidence": 0.8, "symbol": "BTC/USD", "created_at": "2026-03-12T10:00:00"}
        event2 = {"id": "e2", "action": "SELL", "confidence": 0.7, "symbol": "BTC/USD", "created_at": "2026-03-12T11:00:00"}

        results = [
            ReplayResult(event1, "r1", "BUY", 0.8, True),
            ReplayResult(event2, "r2", "BUY", 0.5, False),
        ]

        summary = ReplaySummary(
            replay_group_id="group-1",
            results=results,
            start_time="2026-03-12T00:00:00",
            end_time="2026-03-12T12:00:00",
        )

        d = summary.to_dict()
        assert d["total_events"] == 2
        assert d["matches"] == 1
        assert d["mismatches"] == 1
        assert d["match_rate"] == 50.0


class TestSignalReplayer:
    """Test the SignalReplayer."""

    @pytest.fixture
    def pool(self):
        return AsyncMock()

    @pytest.fixture
    def audit_recorder(self):
        recorder = AsyncMock(spec=AuditRecorder)
        recorder.get_events = AsyncMock(return_value=[])
        recorder._insert_event = AsyncMock(return_value="replay-event-id")
        return recorder

    @pytest.fixture
    def replayer(self, pool, audit_recorder):
        return SignalReplayer(pool, audit_recorder)

    @pytest.mark.asyncio
    async def test_replay_empty_range(self, replayer, audit_recorder):
        """Test replay with no events in the range."""
        audit_recorder.get_events.return_value = []

        start = datetime(2026, 3, 12, 0, 0, 0)
        end = datetime(2026, 3, 12, 12, 0, 0)

        summary = await replayer.replay(start, end)

        assert summary.replay_group_id is not None
        assert len(summary.results) == 0
        d = summary.to_dict()
        assert d["total_events"] == 0

        # Should record REPLAY_STARTED and REPLAY_COMPLETED
        assert audit_recorder._insert_event.call_count == 2
        start_call = audit_recorder._insert_event.call_args_list[0]
        assert start_call.kwargs["event_type"] == "REPLAY_STARTED"
        end_call = audit_recorder._insert_event.call_args_list[1]
        assert end_call.kwargs["event_type"] == "REPLAY_COMPLETED"

    @pytest.mark.asyncio
    async def test_replay_passthrough(self, replayer, audit_recorder):
        """Test passthrough replay (no processor) returns matching results."""
        events = [
            {
                "id": "event-1",
                "signal_id": "sig-1",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "reasoning": "Momentum",
                "strategy_breakdown": [{"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9}],
                "market_state": None,
                "model_used": "gpt-4",
                "tool_calls": None,
                "created_at": "2026-03-12T10:00:00",
            },
        ]
        audit_recorder.get_events.return_value = events

        start = datetime(2026, 3, 12, 0, 0, 0)
        end = datetime(2026, 3, 12, 12, 0, 0)

        summary = await replayer.replay(start, end, symbol="BTC/USD")

        assert len(summary.results) == 1
        assert summary.results[0].match is True
        assert summary.results[0].replay_action == "BUY"

    @pytest.mark.asyncio
    async def test_replay_with_processor(self, replayer, audit_recorder):
        """Test replay with a custom processor that changes the action."""
        events = [
            {
                "id": "event-1",
                "signal_id": "sig-1",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "reasoning": "Momentum",
                "strategy_breakdown": [],
                "market_state": None,
                "model_used": None,
                "tool_calls": None,
                "created_at": "2026-03-12T10:00:00",
            },
        ]
        audit_recorder.get_events.return_value = events

        def reverse_processor(event):
            return {"action": "SELL", "confidence": 0.5}

        start = datetime(2026, 3, 12, 0, 0, 0)
        end = datetime(2026, 3, 12, 12, 0, 0)

        summary = await replayer.replay(start, end, processor=reverse_processor)

        assert len(summary.results) == 1
        assert summary.results[0].match is False
        assert summary.results[0].replay_action == "SELL"
        assert summary.results[0].replay_confidence == 0.5

    @pytest.mark.asyncio
    async def test_replay_multiple_events(self, replayer, audit_recorder):
        """Test replay with multiple events, some matching and some not."""
        events = [
            {
                "id": "event-1",
                "signal_id": "sig-1",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "reasoning": "Momentum",
                "strategy_breakdown": [],
                "market_state": None,
                "model_used": None,
                "tool_calls": None,
                "created_at": "2026-03-12T10:00:00",
            },
            {
                "id": "event-2",
                "signal_id": "sig-2",
                "symbol": "BTC/USD",
                "action": "SELL",
                "confidence": 0.7,
                "reasoning": "Reversal",
                "strategy_breakdown": [],
                "market_state": None,
                "model_used": None,
                "tool_calls": None,
                "created_at": "2026-03-12T11:00:00",
            },
        ]
        audit_recorder.get_events.return_value = events

        def selective_processor(event):
            # Always returns BUY - matches first, mismatches second
            return {"action": "BUY", "confidence": 0.8}

        start = datetime(2026, 3, 12, 0, 0, 0)
        end = datetime(2026, 3, 12, 12, 0, 0)

        summary = await replayer.replay(start, end, processor=selective_processor)

        d = summary.to_dict()
        assert d["total_events"] == 2
        assert d["matches"] == 1
        assert d["mismatches"] == 1
        assert d["match_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_replay_records_is_replay_flag(self, replayer, audit_recorder):
        """Test that replay events are marked with is_replay=True."""
        events = [
            {
                "id": "event-1",
                "signal_id": "sig-1",
                "symbol": "BTC/USD",
                "action": "BUY",
                "confidence": 0.85,
                "reasoning": "Test",
                "strategy_breakdown": [],
                "market_state": None,
                "model_used": None,
                "tool_calls": None,
                "created_at": "2026-03-12T10:00:00",
            },
        ]
        audit_recorder.get_events.return_value = events

        start = datetime(2026, 3, 12, 0, 0, 0)
        end = datetime(2026, 3, 12, 12, 0, 0)

        await replayer.replay(start, end)

        # All _insert_event calls should have is_replay=True
        for call in audit_recorder._insert_event.call_args_list:
            assert call.kwargs["is_replay"] is True

    @pytest.mark.asyncio
    async def test_get_replay_summary(self, replayer, pool):
        """Test getting a replay summary by group ID."""
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        summary_data = {
            "total_events": 5,
            "matches": 4,
            "match_rate": 80.0,
        }
        conn.fetchrow.return_value = {
            "agent_parameters": json.dumps(summary_data),
        }

        result = await replayer.get_replay_summary("group-123")

        assert result is not None
        assert result["total_events"] == 5
        assert result["match_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_replay_summary_not_found(self, replayer, pool):
        """Test getting a non-existent replay summary."""
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetchrow.return_value = None

        result = await replayer.get_replay_summary("nonexistent-group")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_replays(self, replayer, pool):
        """Test listing recent replay sessions."""
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "replay_group_id": "group-1",
            "symbol": "BTC/USD",
            "agent_parameters": json.dumps(
                {"total_events": 10, "match_rate": 90.0}
            ),
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }[key]

        conn.fetch.return_value = [mock_row]

        results = await replayer.list_replays(limit=5)

        assert len(results) == 1
        assert results[0]["replay_group_id"] == "group-1"
        assert results[0]["symbol"] == "BTC/USD"
