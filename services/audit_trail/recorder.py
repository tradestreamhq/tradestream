"""Append-only audit event recorder backed by PostgreSQL."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg

from services.audit_trail.models import AuditEvent, EventType

logger = logging.getLogger(__name__)


class AuditRecorder:
    """Records order lifecycle events immutably to an append-only audit table."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def record(
        self,
        order_id: str,
        event_type: EventType,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Append an audit event. Returns the recorded event."""
        import json

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            order_id=order_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            strategy=strategy,
            details=details or {},
        )

        query = """
            INSERT INTO audit_events
                (event_id, order_id, event_type, timestamp, symbol, strategy, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                event.event_id,
                event.order_id,
                event.event_type.value,
                event.timestamp,
                event.symbol,
                event.strategy,
                json.dumps(event.details),
            )

        logger.info("Audit event recorded: %s for order %s", event_type.value, order_id)
        return event
