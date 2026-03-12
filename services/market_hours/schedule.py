"""Exchange schedules and market phase detection."""

from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from services.market_hours.calendar import get_holiday, is_half_day
from services.market_hours.models import (
    ExchangeSchedule,
    MarketPhase,
    MarketStatus,
    TradingSession,
)

# --- Exchange schedule definitions ---

NYSE_SCHEDULE = ExchangeSchedule(
    exchange="NYSE",
    timezone="America/New_York",
    sessions=[
        TradingSession(MarketPhase.PRE_MARKET, time(4, 0), time(9, 30)),
        TradingSession(MarketPhase.REGULAR, time(9, 30), time(16, 0)),
        TradingSession(MarketPhase.POST_MARKET, time(16, 0), time(20, 0)),
    ],
    half_day_sessions=[
        TradingSession(MarketPhase.PRE_MARKET, time(4, 0), time(9, 30)),
        TradingSession(MarketPhase.REGULAR, time(9, 30), time(13, 0)),
    ],
)

NASDAQ_SCHEDULE = ExchangeSchedule(
    exchange="NASDAQ",
    timezone="America/New_York",
    sessions=[
        TradingSession(MarketPhase.PRE_MARKET, time(4, 0), time(9, 30)),
        TradingSession(MarketPhase.REGULAR, time(9, 30), time(16, 0)),
        TradingSession(MarketPhase.POST_MARKET, time(16, 0), time(20, 0)),
    ],
    half_day_sessions=[
        TradingSession(MarketPhase.PRE_MARKET, time(4, 0), time(9, 30)),
        TradingSession(MarketPhase.REGULAR, time(9, 30), time(13, 0)),
    ],
)

CME_SCHEDULE = ExchangeSchedule(
    exchange="CME",
    timezone="America/Chicago",
    sessions=[
        TradingSession(MarketPhase.REGULAR, time(17, 0), time(23, 59, 59)),
        TradingSession(MarketPhase.REGULAR, time(0, 0), time(16, 0)),
    ],
)

CRYPTO_SCHEDULE = ExchangeSchedule(
    exchange="CRYPTO",
    timezone="UTC",
    sessions=[
        TradingSession(MarketPhase.REGULAR, time(0, 0), time(23, 59, 59)),
    ],
)

SCHEDULES = {
    "NYSE": NYSE_SCHEDULE,
    "NASDAQ": NASDAQ_SCHEDULE,
    "CME": CME_SCHEDULE,
    "CRYPTO": CRYPTO_SCHEDULE,
}


def _time_in_range(t: time, start: time, end: time) -> bool:
    """Check if time t falls within [start, end)."""
    if start <= end:
        return start <= t < end
    # Wraps midnight
    return t >= start or t < end


def get_current_phase(
    exchange: str, now: Optional[datetime] = None
) -> MarketStatus:
    """Determine the current market phase for an exchange.

    Args:
        exchange: Exchange code (NYSE, NASDAQ, CME, CRYPTO).
        now: Current UTC datetime. Defaults to datetime.now(UTC).

    Returns:
        MarketStatus with the current phase and related info.
    """
    exchange = exchange.upper()
    schedule = SCHEDULES.get(exchange)
    if schedule is None:
        raise ValueError(f"Unknown exchange: {exchange}")

    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    tz = ZoneInfo(schedule.timezone)
    local_now = now.astimezone(tz)
    local_time = local_now.time()
    local_date = local_now.date()

    # Crypto is always open
    if exchange == "CRYPTO":
        return MarketStatus(
            exchange=exchange,
            phase=MarketPhase.REGULAR,
            is_open=True,
        )

    # Check for holidays
    holiday = get_holiday(local_date)
    if holiday is not None and not holiday.half_day:
        return MarketStatus(
            exchange=exchange,
            phase=MarketPhase.CLOSED,
            is_open=False,
            is_holiday=True,
            holiday_name=holiday.name,
        )

    # Check for weekends (CME trades Sun-Fri, so only closed Saturday)
    if exchange == "CME":
        if local_now.weekday() == 5:  # Saturday
            return MarketStatus(
                exchange=exchange,
                phase=MarketPhase.CLOSED,
                is_open=False,
            )
    else:
        if local_now.weekday() >= 5:  # Saturday or Sunday
            return MarketStatus(
                exchange=exchange,
                phase=MarketPhase.CLOSED,
                is_open=False,
            )

    # Use half-day sessions if applicable
    use_half_day = holiday is not None and holiday.half_day
    sessions = (
        schedule.half_day_sessions
        if use_half_day and schedule.half_day_sessions
        else schedule.sessions
    )

    # Find matching session
    for session in sessions:
        if _time_in_range(local_time, session.start, session.end):
            return MarketStatus(
                exchange=exchange,
                phase=session.phase,
                is_open=session.phase == MarketPhase.REGULAR,
                current_session_start=session.start.isoformat(),
                current_session_end=session.end.isoformat(),
                is_holiday=use_half_day,
                holiday_name=holiday.name if use_half_day else None,
            )

    return MarketStatus(
        exchange=exchange,
        phase=MarketPhase.CLOSED,
        is_open=False,
        is_holiday=use_half_day,
        holiday_name=holiday.name if use_half_day else None,
    )


def is_market_open(exchange: str, now: Optional[datetime] = None) -> bool:
    """Check if regular trading is active for the given exchange.

    This is the primary helper for strategy code.
    """
    return get_current_phase(exchange, now).is_open
