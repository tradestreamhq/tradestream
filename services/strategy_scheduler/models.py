"""Pydantic models for the Strategy Scheduler service."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MarketPhase(str, Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"


class StrategySchedule(BaseModel):
    """Schedule configuration for a strategy."""

    strategy_id: str = Field(..., description="ID of the strategy")
    active_hours_start: Optional[str] = Field(
        None, description="Start of active hours in HH:MM format (UTC)"
    )
    active_hours_end: Optional[str] = Field(
        None, description="End of active hours in HH:MM format (UTC)"
    )
    market_phases: List[MarketPhase] = Field(
        default_factory=lambda: [MarketPhase.REGULAR],
        description="Market phases during which the strategy should run",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="Custom cron expression for fine-grained scheduling (minute hour day month weekday)",
    )
    timezone: str = Field("UTC", description="Timezone for schedule evaluation")
    enabled: bool = Field(True, description="Whether the schedule is active")


class ScheduleCreate(BaseModel):
    """Request body for creating/updating a schedule."""

    active_hours_start: Optional[str] = Field(
        None, description="Start of active hours in HH:MM format (UTC)"
    )
    active_hours_end: Optional[str] = Field(
        None, description="End of active hours in HH:MM format (UTC)"
    )
    market_phases: List[MarketPhase] = Field(
        default_factory=lambda: [MarketPhase.REGULAR],
        description="Market phases during which the strategy should run",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="Custom cron expression (minute hour day month weekday)",
    )
    timezone: str = Field("UTC", description="Timezone for schedule evaluation")
    enabled: bool = Field(True, description="Whether the schedule is active")


class ScheduleStatus(BaseModel):
    """Current status of a strategy schedule."""

    strategy_id: str
    should_run: bool = Field(
        ..., description="Whether the strategy should be running now"
    )
    current_market_phase: MarketPhase
    in_active_hours: bool
    cron_match: bool
    enabled: bool
    next_activation: Optional[str] = Field(
        None, description="Estimated next activation time (ISO format)"
    )
