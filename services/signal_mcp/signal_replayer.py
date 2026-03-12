"""
Signal replay engine for debugging.
Loads signal events from the audit log and replays them through the pipeline,
comparing replay results with original outcomes.
"""

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import asyncpg
from absl import logging

from services.signal_mcp.audit_recorder import AuditRecorder


class ReplayResult:
    """Result of replaying a single signal event."""

    def __init__(
        self,
        original_event: Dict[str, Any],
        replay_event_id: str,
        replay_action: Optional[str],
        replay_confidence: Optional[float],
        match: bool,
    ):
        self.original_event = original_event
        self.replay_event_id = replay_event_id
        self.replay_action = replay_action
        self.replay_confidence = replay_confidence
        self.match = match

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_event_id": self.original_event["id"],
            "original_action": self.original_event.get("action"),
            "original_confidence": self.original_event.get("confidence"),
            "replay_event_id": self.replay_event_id,
            "replay_action": self.replay_action,
            "replay_confidence": self.replay_confidence,
            "match": self.match,
            "symbol": self.original_event.get("symbol"),
            "original_timestamp": self.original_event.get("created_at"),
        }


class ReplaySummary:
    """Summary of a complete replay session."""

    def __init__(
        self,
        replay_group_id: str,
        results: List[ReplayResult],
        start_time: str,
        end_time: str,
    ):
        self.replay_group_id = replay_group_id
        self.results = results
        self.start_time = start_time
        self.end_time = end_time

    def to_dict(self) -> Dict[str, Any]:
        total = len(self.results)
        matches = sum(1 for r in self.results if r.match)
        return {
            "replay_group_id": self.replay_group_id,
            "total_events": total,
            "matches": matches,
            "mismatches": total - matches,
            "match_rate": round(matches / total * 100, 2) if total > 0 else 0.0,
            "time_range": {
                "start": self.start_time,
                "end": self.end_time,
            },
            "results": [r.to_dict() for r in self.results],
        }


# Type alias for the signal processing callback used during replay.
SignalProcessor = Callable[[Dict[str, Any]], Dict[str, Any]]


class SignalReplayer:
    """Replays signal sequences from the audit log for debugging."""

    def __init__(self, pool: asyncpg.Pool, audit_recorder: AuditRecorder):
        self._pool = pool
        self._audit_recorder = audit_recorder

    async def replay(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: Optional[str] = None,
        processor: Optional[SignalProcessor] = None,
    ) -> ReplaySummary:
        """Replay signals from a time range through the pipeline.

        Args:
            start_time: Start of the replay window.
            end_time: End of the replay window.
            symbol: Optional symbol filter.
            processor: Optional callback that processes a signal event and
                returns a dict with 'action' and 'confidence'. If None,
                the original values are echoed back (passthrough replay).

        Returns:
            ReplaySummary with comparison results.
        """
        replay_group_id = str(uuid4())

        logging.info(
            "Starting replay %s for %s from %s to %s",
            replay_group_id,
            symbol or "all symbols",
            start_time.isoformat(),
            end_time.isoformat(),
        )

        # Record replay start
        await self._audit_recorder._insert_event(
            event_type="REPLAY_STARTED",
            symbol=symbol or "*",
            agent_parameters={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "symbol": symbol,
            },
            replay_group_id=replay_group_id,
            is_replay=True,
        )

        # Load original events
        events = await self._audit_recorder.get_events(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            event_types=["SIGNAL_EMITTED"],
            limit=10000,
            exclude_replays=True,
        )

        logging.info(
            "Replay %s: loaded %d events to replay", replay_group_id, len(events)
        )

        results = []
        for event in events:
            result = await self._replay_single_event(
                event, replay_group_id, processor
            )
            results.append(result)

        # Record replay completion
        summary = ReplaySummary(
            replay_group_id=replay_group_id,
            results=results,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        await self._audit_recorder._insert_event(
            event_type="REPLAY_COMPLETED",
            symbol=symbol or "*",
            agent_parameters=summary.to_dict(),
            replay_group_id=replay_group_id,
            is_replay=True,
        )

        logging.info(
            "Replay %s completed: %d events, %d matches, %d mismatches",
            replay_group_id,
            len(results),
            sum(1 for r in results if r.match),
            sum(1 for r in results if not r.match),
        )

        return summary

    async def get_replay_summary(
        self, replay_group_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the summary of a previous replay session.

        Returns:
            The replay summary dict, or None if not found.
        """
        query = """
        SELECT agent_parameters
        FROM signal_audit_log
        WHERE replay_group_id = $1
            AND event_type = 'REPLAY_COMPLETED'
        LIMIT 1
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, replay_group_id)
            if row and row["agent_parameters"]:
                return json.loads(row["agent_parameters"])
            return None

    async def list_replays(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent replay sessions.

        Returns:
            List of replay metadata dicts.
        """
        query = """
        SELECT replay_group_id, symbol, agent_parameters, created_at
        FROM signal_audit_log
        WHERE event_type = 'REPLAY_COMPLETED'
            AND replay_group_id IS NOT NULL
        ORDER BY created_at DESC
        LIMIT $1
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            results = []
            for row in rows:
                params = (
                    json.loads(row["agent_parameters"])
                    if row["agent_parameters"]
                    else {}
                )
                results.append(
                    {
                        "replay_group_id": str(row["replay_group_id"]),
                        "symbol": row["symbol"],
                        "total_events": params.get("total_events", 0),
                        "match_rate": params.get("match_rate", 0.0),
                        "created_at": (
                            row["created_at"].isoformat()
                            if row["created_at"]
                            else None
                        ),
                    }
                )
            return results

    async def _replay_single_event(
        self,
        event: Dict[str, Any],
        replay_group_id: str,
        processor: Optional[SignalProcessor],
    ) -> ReplayResult:
        """Replay a single signal event and compare with original."""
        if processor:
            replay_output = processor(event)
            replay_action = replay_output.get("action")
            replay_confidence = replay_output.get("confidence")
        else:
            # Passthrough: echo original values
            replay_action = event.get("action")
            replay_confidence = event.get("confidence")

        match = replay_action == event.get("action")

        # Record the replay event
        replay_event_id = await self._audit_recorder._insert_event(
            event_type="SIGNAL_EMITTED",
            signal_id=event.get("signal_id"),
            symbol=event["symbol"],
            action=replay_action,
            confidence=replay_confidence,
            reasoning=f"Replay of event {event['id']}",
            strategy_breakdown=event.get("strategy_breakdown"),
            market_state=event.get("market_state"),
            model_used=event.get("model_used"),
            tool_calls=event.get("tool_calls"),
            replay_group_id=replay_group_id,
            is_replay=True,
            original_event_id=event["id"],
        )

        return ReplayResult(
            original_event=event,
            replay_event_id=replay_event_id,
            replay_action=replay_action,
            replay_confidence=replay_confidence,
            match=match,
        )
