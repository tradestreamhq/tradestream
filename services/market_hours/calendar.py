"""US market holiday calendar for 2026 and 2027."""

from datetime import date
from typing import Dict, Optional

from services.market_hours.models import Holiday

# US market holidays (NYSE/NASDAQ).
# Half days: day before Independence Day, day after Thanksgiving, Christmas Eve.
_HOLIDAYS: Dict[date, Holiday] = {
    # 2026
    date(2026, 1, 1): Holiday(date(2026, 1, 1), "New Year's Day"),
    date(2026, 1, 19): Holiday(date(2026, 1, 19), "Martin Luther King Jr. Day"),
    date(2026, 2, 16): Holiday(date(2026, 2, 16), "Presidents' Day"),
    date(2026, 4, 3): Holiday(date(2026, 4, 3), "Good Friday"),
    date(2026, 5, 25): Holiday(date(2026, 5, 25), "Memorial Day"),
    date(2026, 6, 19): Holiday(date(2026, 6, 19), "Juneteenth"),
    date(2026, 7, 3): Holiday(date(2026, 7, 3), "Independence Day (observed)", half_day=True),
    date(2026, 7, 4): Holiday(date(2026, 7, 4), "Independence Day"),
    date(2026, 9, 7): Holiday(date(2026, 9, 7), "Labor Day"),
    date(2026, 11, 26): Holiday(date(2026, 11, 26), "Thanksgiving Day"),
    date(2026, 11, 27): Holiday(date(2026, 11, 27), "Day After Thanksgiving", half_day=True),
    date(2026, 12, 24): Holiday(date(2026, 12, 24), "Christmas Eve", half_day=True),
    date(2026, 12, 25): Holiday(date(2026, 12, 25), "Christmas Day"),
    # 2027
    date(2027, 1, 1): Holiday(date(2027, 1, 1), "New Year's Day"),
    date(2027, 1, 18): Holiday(date(2027, 1, 18), "Martin Luther King Jr. Day"),
    date(2027, 2, 15): Holiday(date(2027, 2, 15), "Presidents' Day"),
    date(2027, 3, 26): Holiday(date(2027, 3, 26), "Good Friday"),
    date(2027, 5, 31): Holiday(date(2027, 5, 31), "Memorial Day"),
    date(2027, 6, 18): Holiday(date(2027, 6, 18), "Juneteenth (observed)"),
    date(2027, 7, 2): Holiday(date(2027, 7, 2), "Independence Day (observed)", half_day=True),
    date(2027, 7, 5): Holiday(date(2027, 7, 5), "Independence Day (observed)"),
    date(2027, 9, 6): Holiday(date(2027, 9, 6), "Labor Day"),
    date(2027, 11, 25): Holiday(date(2027, 11, 25), "Thanksgiving Day"),
    date(2027, 11, 26): Holiday(date(2027, 11, 26), "Day After Thanksgiving", half_day=True),
    date(2027, 12, 24): Holiday(date(2027, 12, 24), "Christmas Day (observed)"),
}


def get_holiday(d: date) -> Optional[Holiday]:
    """Return the Holiday for the given date, or None."""
    return _HOLIDAYS.get(d)


def is_half_day(d: date) -> bool:
    """Return True if the given date is a half trading day."""
    h = _HOLIDAYS.get(d)
    return h is not None and h.half_day


def get_holidays(year: int) -> list[Holiday]:
    """Return all holidays for the given year, sorted by date."""
    return sorted(
        (h for h in _HOLIDAYS.values() if h.date.year == year),
        key=lambda h: h.date,
    )
