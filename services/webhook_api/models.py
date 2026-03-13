"""Webhook data models and Pydantic schemas."""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class WebhookEvent(str, enum.Enum):
    """Supported webhook event types."""

    SIGNAL_GENERATED = "signal_generated"
    TRADE_EXECUTED = "trade_executed"
    ALERT_TRIGGERED = "alert_triggered"
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"


class WebhookCreate(BaseModel):
    """Request body for creating a webhook."""

    url: HttpUrl = Field(..., description="URL to receive webhook payloads")
    events: List[WebhookEvent] = Field(
        ..., min_length=1, description="Event types to subscribe to"
    )
    description: str = Field("", description="Optional description")
    is_active: bool = Field(True, description="Whether the webhook is active")


class WebhookUpdate(BaseModel):
    """Request body for updating a webhook."""

    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEvent]] = Field(None, min_length=1)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Webhook resource representation."""

    id: uuid.UUID
    url: str
    events: List[str]
    description: str
    is_active: bool
    signing_secret: str
    created_at: datetime
    updated_at: datetime


class DeliveryStatus(str, enum.Enum):
    """Webhook delivery status."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
