"""
Tests for the signal audit recorder.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.signal_mcp.audit_recorder import AuditRecorder


class TestAuditRecorder:
    """Test cases for the AuditRecorder."""

    @pytest.fixture
    def pool(self):
        """Create a mock asyncpg pool."""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return pool

    @pytest.fixture
    def conn(self, pool):
        """Get the mock connection from the pool."""
        return pool.acquire.return_value.__aenter__.return_value

    @pytest.fixture
    def recorder(self, pool):
        """Create an AuditRecorder instance."""
        return AuditRecorder(pool)

    @pytest.mark.asyncio
    async def test_record_signal_emitted(self, recorder, conn):
        """Test recording a signal emission event."""
        conn.fetchrow.return_value = {"id": "audit-uuid-1"}

        event_id = await recorder.record_signal_emitted(
            signal_id="signal-uuid-1",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.85,
            reasoning="Strong momentum",
            strategy_breakdown=[
                {"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9}
            ],
        )

        assert event_id == "audit-uuid-1"
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        assert call_args[0][1] == "SIGNAL_EMITTED"
        assert call_args[0][2] == "signal-uuid-1"
        assert call_args[0][3] == "BTC/USD"
        assert call_args[0][4] == "BUY"
        assert call_args[0][5] == Decimal("0.85")

    @pytest.mark.asyncio
    async def test_record_signal_skipped(self, recorder, conn):
        """Test recording a skipped signal event."""
        conn.fetchrow.return_value = {"id": "audit-uuid-2"}

        event_id = await recorder.record_signal_skipped(
            symbol="ETH/USD",
            action="SELL",
            confidence=0.7,
            reasoning="Duplicate within 15 minutes",
        )

        assert event_id == "audit-uuid-2"
        call_args = conn.fetchrow.call_args
        assert call_args[0][1] == "SIGNAL_SKIPPED"
        assert call_args[0][2] is None  # no signal_id for skipped
        assert call_args[0][3] == "ETH/USD"

    @pytest.mark.asyncio
    async def test_record_decision_logged(self, recorder, conn):
        """Test recording a decision logging event."""
        conn.fetchrow.return_value = {"id": "audit-uuid-3"}

        event_id = await recorder.record_decision_logged(
            signal_id="signal-uuid-1",
            symbol="BTC/USD",
            model_used="gpt-4",
            tool_calls=[{"name": "get_candles", "args": {"symbol": "BTC/USD"}}],
        )

        assert event_id == "audit-uuid-3"
        call_args = conn.fetchrow.call_args
        assert call_args[0][1] == "DECISION_LOGGED"

    @pytest.mark.asyncio
    async def test_record_with_market_state(self, recorder, conn):
        """Test recording an event with market state context."""
        conn.fetchrow.return_value = {"id": "audit-uuid-4"}

        market_state = {"price": 50000.0, "volume": 1200.5, "volatility": "moderate"}

        event_id = await recorder.record_signal_emitted(
            signal_id="signal-uuid-2",
            symbol="BTC/USD",
            action="BUY",
            confidence=0.9,
            reasoning="High volume breakout",
            strategy_breakdown=[],
            market_state=market_state,
        )

        assert event_id == "audit-uuid-4"
        call_args = conn.fetchrow.call_args
        # market_state is the 8th positional arg (index 8)
        assert json.loads(call_args[0][8]) == market_state

    @pytest.mark.asyncio
    async def test_get_events_no_filters(self, recorder, conn):
        """Test getting events with no filters."""
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "id": "audit-uuid-1",
            "sequence_number": 1,
            "event_type": "SIGNAL_EMITTED",
            "signal_id": "signal-uuid-1",
            "symbol": "BTC/USD",
            "action": "BUY",
            "confidence": Decimal("0.85"),
            "reasoning": "Strong momentum",
            "strategy_breakdown": json.dumps(
                [{"strategy_type": "MACD", "signal": "BUY", "confidence": 0.9}]
            ),
            "market_state": None,
            "model_used": None,
            "tool_calls": None,
            "agent_parameters": None,
            "replay_group_id": None,
            "is_replay": False,
            "original_event_id": None,
            "created_at": datetime(2026, 3, 12, 10, 0, 0),
        }[key]

        conn.fetch.return_value = [mock_row]

        events = await recorder.get_events(limit=50)

        assert len(events) == 1
        assert events[0]["event_type"] == "SIGNAL_EMITTED"
        assert events[0]["symbol"] == "BTC/USD"
        assert events[0]["is_replay"] is False

    @pytest.mark.asyncio
    async def test_get_events_with_symbol_filter(self, recorder, conn):
        """Test getting events filtered by symbol."""
        conn.fetch.return_value = []

        events = await recorder.get_events(
            symbol="ETH/USD",
            limit=10,
        )

        assert events == []
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "symbol = $" in query

    @pytest.mark.asyncio
    async def test_get_events_with_time_range(self, recorder, conn):
        """Test getting events with time range filter."""
        conn.fetch.return_value = []

        start = datetime(2026, 3, 1, 0, 0, 0)
        end = datetime(2026, 3, 12, 0, 0, 0)

        events = await recorder.get_events(
            start_time=start,
            end_time=end,
        )

        assert events == []
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "created_at >=" in query
        assert "created_at <=" in query

    @pytest.mark.asyncio
    async def test_get_events_with_event_type_filter(self, recorder, conn):
        """Test getting events filtered by event type."""
        conn.fetch.return_value = []

        events = await recorder.get_events(
            event_types=["SIGNAL_EMITTED", "SIGNAL_SKIPPED"],
        )

        assert events == []
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "event_type = ANY" in query

    @pytest.mark.asyncio
    async def test_get_events_excludes_replays_by_default(self, recorder, conn):
        """Test that replays are excluded by default."""
        conn.fetch.return_value = []

        await recorder.get_events()

        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "is_replay = FALSE" in query

    @pytest.mark.asyncio
    async def test_get_events_includes_replays(self, recorder, conn):
        """Test that replays can be included."""
        conn.fetch.return_value = []

        await recorder.get_events(exclude_replays=False)

        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "is_replay = FALSE" not in query
