"""Query interface for audit trail events."""

import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg

from services.audit_trail.models import AuditEvent, AuditSearchParams, EventType

logger = logging.getLogger(__name__)


class AuditQuery:
    """Read-only query interface for the audit event store."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def get_order_trail(self, order_id: str) -> List[Dict[str, Any]]:
        """Return the full audit trail for an order, ordered by timestamp."""
        query = """
            SELECT event_id, order_id, event_type, timestamp, symbol, strategy, details
            FROM audit_events
            WHERE order_id = $1
            ORDER BY timestamp ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, order_id)
        return [self._row_to_dict(row) for row in rows]

    async def search(self, params: AuditSearchParams) -> List[Dict[str, Any]]:
        """Search audit events by date range, strategy, symbol, or event type."""
        conditions = []
        args = []
        idx = 1

        if params.start_date is not None:
            conditions.append(f"timestamp >= ${idx}")
            args.append(params.start_date)
            idx += 1

        if params.end_date is not None:
            conditions.append(f"timestamp <= ${idx}")
            args.append(params.end_date)
            idx += 1

        if params.strategy is not None:
            conditions.append(f"strategy = ${idx}")
            args.append(params.strategy)
            idx += 1

        if params.symbol is not None:
            conditions.append(f"symbol = ${idx}")
            args.append(params.symbol)
            idx += 1

        if params.event_type is not None:
            conditions.append(f"event_type = ${idx}")
            args.append(params.event_type.value)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT event_id, order_id, event_type, timestamp, symbol, strategy, details
            FROM audit_events
            {where}
            ORDER BY timestamp DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        args.extend([params.limit, params.offset])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [self._row_to_dict(row) for row in rows]

    async def export_csv(self, params: AuditSearchParams) -> str:
        """Export matching audit events as a CSV string for compliance reporting."""
        events = await self.search(params)

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "event_id",
                "order_id",
                "event_type",
                "timestamp",
                "symbol",
                "strategy",
                "details",
            ],
        )
        writer.writeheader()
        for event in events:
            row = dict(event)
            if isinstance(row.get("details"), dict):
                row["details"] = json.dumps(row["details"])
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        item = dict(row)
        if item.get("timestamp"):
            item["timestamp"] = item["timestamp"].isoformat()
        if isinstance(item.get("details"), str):
            try:
                item["details"] = json.loads(item["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        return item
