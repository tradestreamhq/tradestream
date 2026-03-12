"""
Signal audit recorder for append-only event logging.
Records every signal event with full context for replay and debugging.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import asyncpg
from absl import logging


class AuditRecorder:
    """Records signal events to the signal_audit_log table."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def record_signal_emitted(
        self,
        signal_id: str,
        symbol: str,
        action: str,
        confidence: float,
        reasoning: str,
        strategy_breakdown: List[Dict[str, Any]],
        market_state: Optional[Dict[str, Any]] = None,
        model_used: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        agent_parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a signal emission event.

        Returns:
            The UUID of the audit log entry.
        """
        return await self._insert_event(
            event_type="SIGNAL_EMITTED",
            signal_id=signal_id,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            strategy_breakdown=strategy_breakdown,
            market_state=market_state,
            model_used=model_used,
            tool_calls=tool_calls,
            agent_parameters=agent_parameters,
        )

    async def record_signal_skipped(
        self,
        symbol: str,
        action: str,
        confidence: float,
        reasoning: str,
        strategy_breakdown: Optional[List[Dict[str, Any]]] = None,
        market_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a skipped signal (e.g., duplicate within 15 minutes).

        Returns:
            The UUID of the audit log entry.
        """
        return await self._insert_event(
            event_type="SIGNAL_SKIPPED",
            signal_id=None,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            strategy_breakdown=strategy_breakdown,
            market_state=market_state,
        )

    async def record_decision_logged(
        self,
        signal_id: str,
        symbol: str,
        model_used: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Record that an agent decision was logged for a signal.

        Returns:
            The UUID of the audit log entry.
        """
        return await self._insert_event(
            event_type="DECISION_LOGGED",
            signal_id=signal_id,
            symbol=symbol,
            model_used=model_used,
            tool_calls=tool_calls,
        )

    async def get_events(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100,
        exclude_replays: bool = True,
    ) -> List[Dict[str, Any]]:
        """Query audit log events with filters.

        Returns:
            List of audit log events ordered by sequence number.
        """
        conditions = []
        params = []
        param_idx = 1

        if exclude_replays:
            conditions.append("is_replay = FALSE")

        if symbol:
            conditions.append(f"symbol = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        if start_time:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(start_time)
            param_idx += 1

        if end_time:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(end_time)
            param_idx += 1

        if event_types:
            conditions.append(f"event_type = ANY(${param_idx})")
            params.append(event_types)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            id, sequence_number, event_type, signal_id,
            symbol, action, confidence, reasoning,
            strategy_breakdown, market_state,
            model_used, tool_calls, agent_parameters,
            replay_group_id, is_replay, original_event_id,
            created_at
        FROM signal_audit_log
        {where_clause}
        ORDER BY sequence_number ASC
        LIMIT ${param_idx}
        """
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_dict(row) for row in rows]

    async def _insert_event(
        self,
        event_type: str,
        symbol: str,
        signal_id: Optional[str] = None,
        action: Optional[str] = None,
        confidence: Optional[float] = None,
        reasoning: Optional[str] = None,
        strategy_breakdown: Optional[List[Dict[str, Any]]] = None,
        market_state: Optional[Dict[str, Any]] = None,
        model_used: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        agent_parameters: Optional[Dict[str, Any]] = None,
        replay_group_id: Optional[str] = None,
        is_replay: bool = False,
        original_event_id: Optional[str] = None,
    ) -> str:
        """Insert an event into the audit log.

        Returns:
            The UUID of the inserted event.
        """
        query = """
        INSERT INTO signal_audit_log (
            event_type, signal_id, symbol, action, confidence,
            reasoning, strategy_breakdown, market_state,
            model_used, tool_calls, agent_parameters,
            replay_group_id, is_replay, original_event_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                event_type,
                signal_id,
                symbol,
                action,
                Decimal(str(confidence)) if confidence is not None else None,
                reasoning,
                json.dumps(strategy_breakdown) if strategy_breakdown else None,
                json.dumps(market_state) if market_state else None,
                model_used,
                json.dumps(tool_calls) if tool_calls else None,
                json.dumps(agent_parameters) if agent_parameters else None,
                replay_group_id,
                is_replay,
                original_event_id,
            )
            event_id = str(row["id"])
            logging.info(
                "Audit log: %s event %s for %s", event_type, event_id, symbol
            )
            return event_id

    @staticmethod
    def _row_to_dict(row: asyncpg.Record) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = {
            "id": str(row["id"]),
            "sequence_number": row["sequence_number"],
            "event_type": row["event_type"],
            "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
            "symbol": row["symbol"],
            "action": row["action"],
            "confidence": (
                float(row["confidence"]) if row["confidence"] is not None else None
            ),
            "reasoning": row["reasoning"],
            "strategy_breakdown": (
                json.loads(row["strategy_breakdown"])
                if row["strategy_breakdown"]
                else None
            ),
            "market_state": (
                json.loads(row["market_state"]) if row["market_state"] else None
            ),
            "model_used": row["model_used"],
            "tool_calls": (
                json.loads(row["tool_calls"]) if row["tool_calls"] else None
            ),
            "agent_parameters": (
                json.loads(row["agent_parameters"])
                if row["agent_parameters"]
                else None
            ),
            "replay_group_id": (
                str(row["replay_group_id"]) if row["replay_group_id"] else None
            ),
            "is_replay": row["is_replay"],
            "original_event_id": (
                str(row["original_event_id"]) if row["original_event_id"] else None
            ),
            "created_at": (
                row["created_at"].isoformat() if row["created_at"] else None
            ),
        }
        return result
