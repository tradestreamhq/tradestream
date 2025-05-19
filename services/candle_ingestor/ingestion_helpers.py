from datetime import datetime, timedelta, timezone
import re

from absl import logging


def get_tiingo_resample_freq(granularity_minutes: int) -> str:
    """Converts candle granularity in minutes to Tiingo's resampleFreq string."""
    if granularity_minutes >= 1440:  # 1 day = 24 * 60
        days = granularity_minutes // 1440
        return f"{days}day"
    elif granularity_minutes >= 60:  # 1 hour
        hours = granularity_minutes // 60
        return f"{hours}hour"
    elif granularity_minutes > 0:
        return f"{granularity_minutes}min"
    else:
        logging.warning(
            f"Invalid candle_granularity_minutes: {granularity_minutes}. Defaulting to '1min'."
        )
        return "1min"


def parse_backfill_start_date(date_str: str) -> datetime:
    """
    Parses a flexible start date string to a timezone-aware datetime object (UTC).
    Supports "YYYY-MM-DD", "X_days_ago", "X_weeks_ago", "X_months_ago", "X_years_ago".
    """
    now = datetime.now(timezone.utc)
    date_str_lower = date_str.lower()

    if re.match(r"^\d+_days_ago$", date_str_lower):
        days = int(date_str_lower.split("_")[0])
        return now - timedelta(days=days)
    elif re.match(r"^\d+_weeks_ago$", date_str_lower):
        weeks = int(date_str_lower.split("_")[0])
        return now - timedelta(weeks=weeks)
    elif re.match(r"^\d+_months_ago$", date_str_lower):
        months = int(date_str_lower.split("_")[0])
        # Approximate months as 30 days for timedelta.
        # For more precision, consider `from dateutil.relativedelta import relativedelta`
        # and `return now - relativedelta(months=months)`
        return now - timedelta(days=months * 30)
    elif re.match(r"^\d+_years_ago$", date_str_lower):
        years = int(date_str_lower.split("_")[0])
        # For more precision, consider `from dateutil.relativedelta import relativedelta`
        # and `return now - relativedelta(years=years)`
        return now - timedelta(days=years * 365)

    try:
        # Attempt to parse as YYYY-MM-DD
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)  # Make it timezone-aware UTC
    except ValueError:
        logging.error(
            f"Invalid backfill_start_date format: {date_str}. "
            "Supported formats: YYYY-MM-DD, X_days_ago, X_weeks_ago, X_months_ago, X_years_ago. "
            "Defaulting to 1 year ago."
        )
        return now - timedelta(days=365)
