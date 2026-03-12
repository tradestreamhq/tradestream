"""Strategy Scheduler — evaluates schedules against current time and market state."""

import re
from datetime import datetime, timezone
from typing import Optional

from services.strategy_scheduler.models import MarketPhase


# US equity market hours in UTC (Eastern + 5h / +4h DST).
# Using fixed UTC windows; a production system would handle DST properly.
_PRE_MARKET_START = 9  # 04:00 ET
_REGULAR_START = 14  # 09:30 ET (rounded to hour for simplicity)
_REGULAR_END = 21  # 16:00 ET
_POST_MARKET_END = 1  # 20:00 ET (next day UTC)

_CRON_FIELD_COUNT = 5
_CRON_PATTERN = re.compile(
    r"^[\d,\-\*/]+(\s+[\d,\-\*/]+){4}$"
)


def current_market_phase(now: Optional[datetime] = None) -> MarketPhase:
    """Determine the current market phase based on UTC hour."""
    if now is None:
        now = datetime.now(timezone.utc)
    hour = now.hour
    if _PRE_MARKET_START <= hour < _REGULAR_START:
        return MarketPhase.PRE_MARKET
    if _REGULAR_START <= hour < _REGULAR_END:
        return MarketPhase.REGULAR
    if _REGULAR_END <= hour or hour < _POST_MARKET_END:
        return MarketPhase.POST_MARKET
    return MarketPhase.CLOSED


def is_in_active_hours(
    now: datetime,
    start: Optional[str],
    end: Optional[str],
) -> bool:
    """Check if *now* falls within the active hours window.

    *start* and *end* are ``"HH:MM"`` strings in UTC.
    If both are ``None`` the strategy is always considered in-hours.
    """
    if start is None and end is None:
        return True
    current_time = now.strftime("%H:%M")
    s = start or "00:00"
    e = end or "23:59"
    if s <= e:
        return s <= current_time <= e
    # Overnight window (e.g. 22:00 -> 06:00)
    return current_time >= s or current_time <= e


def validate_cron(expression: str) -> bool:
    """Return True if *expression* looks like a valid 5-field cron string."""
    return bool(_CRON_PATTERN.match(expression.strip()))


def _match_cron_field(field: str, value: int) -> bool:
    """Check if a single cron field matches a given value."""
    if field == "*":
        return True
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                if value % step == 0:
                    return True
            else:
                if value >= int(base) and (value - int(base)) % step == 0:
                    return True
        elif "-" in part:
            lo, hi = part.split("-", 1)
            if int(lo) <= value <= int(hi):
                return True
        else:
            if value == int(part):
                return True
    return False


def cron_matches(expression: str, now: Optional[datetime] = None) -> bool:
    """Evaluate a 5-field cron expression against *now* (UTC).

    Fields: minute  hour  day-of-month  month  day-of-week (0=Mon … 6=Sun)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    fields = expression.strip().split()
    if len(fields) != _CRON_FIELD_COUNT:
        return False
    values = [
        now.minute,
        now.hour,
        now.day,
        now.month,
        now.weekday(),  # 0=Monday
    ]
    return all(_match_cron_field(f, v) for f, v in zip(fields, values))


def should_strategy_run(
    *,
    enabled: bool,
    market_phases: list[MarketPhase],
    active_hours_start: Optional[str],
    active_hours_end: Optional[str],
    cron_expression: Optional[str],
    now: Optional[datetime] = None,
) -> tuple[bool, MarketPhase, bool, bool]:
    """Decide whether a strategy should be running right now.

    Returns ``(should_run, current_phase, in_active_hours, cron_ok)``.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not enabled:
        phase = current_market_phase(now)
        return False, phase, False, False

    phase = current_market_phase(now)
    phase_ok = phase in market_phases
    hours_ok = is_in_active_hours(now, active_hours_start, active_hours_end)
    cron_ok = cron_matches(cron_expression, now) if cron_expression else True

    return (phase_ok and hours_ok and cron_ok), phase, hours_ok, cron_ok
