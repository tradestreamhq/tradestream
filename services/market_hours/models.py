"""Data models for market hours service."""

from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from typing import Dict, List, Optional


class MarketPhase(str, Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"


@dataclass(frozen=True)
class TradingSession:
    """A named trading window with start/end times in exchange-local time."""

    phase: MarketPhase
    start: time
    end: time


@dataclass(frozen=True)
class ExchangeSchedule:
    """Full daily schedule for an exchange."""

    exchange: str
    timezone: str
    sessions: List[TradingSession]
    half_day_sessions: Optional[List[TradingSession]] = None


@dataclass(frozen=True)
class Holiday:
    """A market holiday."""

    date: date
    name: str
    half_day: bool = False


@dataclass(frozen=True)
class MarketStatus:
    """Current status of an exchange."""

    exchange: str
    phase: MarketPhase
    is_open: bool
    current_session_start: Optional[str] = None
    current_session_end: Optional[str] = None
    next_open: Optional[str] = None
    is_holiday: bool = False
    holiday_name: Optional[str] = None
