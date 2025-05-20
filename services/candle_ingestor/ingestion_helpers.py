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
    
    logging.debug(f"Parsing backfill_start_date: {date_str_lower}")

    # Match X_day_ago or X_days_ago (singular or plural)
    if re.match(r"^\d+_days?_ago$", date_str_lower):
        days = int(date_str_lower.split("_")[0])
        logging.debug(f"Matched X_day(s)_ago pattern, days={days}")
        return now - timedelta(days=days)
    
    # Match X_week_ago or X_weeks_ago
    elif re.match(r"^\d+_weeks?_ago$", date_str_lower):
        weeks = int(date_str_lower.split("_")[0])
        logging.debug(f"Matched X_week(s)_ago pattern, weeks={weeks}")
        return now - timedelta(weeks=weeks)
    
    # Match X_month_ago or X_months_ago
    elif re.match(r"^\d+_months?_ago$", date_str_lower):
        months = int(date_str_lower.split("_")[0])
        logging.debug(f"Matched X_month(s)_ago pattern, months={months}")
        # Approximate months as 30 days for timedelta.
        # For more precision, consider `from dateutil.relativedelta import relativedelta`
        # and `return now - relativedelta(months=months)`
        return now - timedelta(days=months * 30)
    
    # Match X_year_ago or X_years_ago
    elif re.match(r"^\d+_years?_ago$", date_str_lower):
        years = int(date_str_lower.split("_")[0])
        logging.debug(f"Matched X_year(s)_ago pattern, years={years}")
        # For more precision, consider `from dateutil.relativedelta import relativedelta`
        # and `return now - relativedelta(years=years)`
        return now - timedelta(days=years * 365)

    try:
        # Attempt to parse as YYYY-MM-DD
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        logging.debug(f"Parsed as YYYY-MM-DD: {dt.isoformat()}")
        return dt.replace(tzinfo=timezone.utc)  # Make it timezone-aware UTC
    except ValueError:
        logging.error(
            f"Invalid backfill_start_date format: {date_str}. "
            "Supported formats: YYYY-MM-DD, X_days_ago, X_weeks_ago, X_months_ago, X_years_ago. "
            "Defaulting to 1 year ago."
        )
        return now - timedelta(days=365)
