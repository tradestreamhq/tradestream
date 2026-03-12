"""Audit trail event models for trade execution compliance logging."""

import enum
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventType(str, enum.Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class AuditEvent(BaseModel):
    """Immutable record of a single order lifecycle event."""

    event_id: str = Field(..., description="Unique event identifier")
    order_id: str = Field(..., description="Associated order identifier")
    event_type: EventType = Field(..., description="Order lifecycle event type")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event",
    )
    symbol: Optional[str] = Field(None, description="Trading instrument symbol")
    strategy: Optional[str] = Field(
        None, description="Strategy that generated the order"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional event context as JSON"
    )


class AuditSearchParams(BaseModel):
    """Query parameters for searching audit events."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    strategy: Optional[str] = None
    symbol: Optional[str] = None
    event_type: Optional[EventType] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
