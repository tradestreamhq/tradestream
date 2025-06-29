import unittest
from datetime import datetime, timedelta, timezone

# Updated import to reflect the new module name
from services.candle_ingestor import ingestion_helpers


class TestIngestionHelpers(unittest.TestCase):
    def test_get_tiingo_resample_freq(self):
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(1), "1min")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(5), "5min")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(60), "1hour")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(120), "2hour")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(1440), "1day")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(2880), "2day")
        # Test default/invalid cases
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(0), "1min")
        self.assertEqual(ingestion_helpers.get_tiingo_resample_freq(-5), "1min")

    def test_parse_backfill_start_date_specific_date(self):
        expected_dt = datetime(2023, 1, 15, tzinfo=timezone.utc)
        self.assertEqual(
            ingestion_helpers.parse_backfill_start_date("2023-01-15"),
            expected_dt,
        )

    def test_parse_backfill_start_date_days_ago(self):
        now = datetime.now(timezone.utc)
        expected_dt = now - timedelta(days=7)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("7_days_ago")
        # Compare date parts to avoid microsecond differences in test runs
        self.assertEqual(parsed_dt.date(), expected_dt.date())

    def test_parse_backfill_start_date_weeks_ago(self):
        now = datetime.now(timezone.utc)
        expected_dt = now - timedelta(weeks=2)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("2_weeks_ago")
        self.assertEqual(parsed_dt.date(), expected_dt.date())

    def test_parse_backfill_start_date_months_ago_approx(self):
        now = datetime.now(timezone.utc)
        # Approximation: 3 months ago is roughly 90 days
        expected_dt_approx = now - timedelta(days=3 * 30)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("3_months_ago")
        # Check if it's close, e.g., within a few days due to 30-day approximation
        self.assertAlmostEqual(
            parsed_dt.timestamp(),
            expected_dt_approx.timestamp(),
            delta=timedelta(
                days=5
            ).total_seconds(),  # Allow some leeway for month length variation
        )

    def test_parse_backfill_start_date_years_ago_approx(self):
        now = datetime.now(timezone.utc)
        expected_dt_approx = now - timedelta(days=2 * 365)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("2_years_ago")
        self.assertAlmostEqual(
            parsed_dt.timestamp(),
            expected_dt_approx.timestamp(),
            delta=timedelta(days=2).total_seconds(),  # Allow for leap year variance
        )

    def test_parse_backfill_start_date_invalid_format_defaults_to_1_year_ago(self):
        now = datetime.now(timezone.utc)
        # Default to 1 year ago
        expected_dt_approx = now - timedelta(days=365)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("invalid_date_format")
        self.assertAlmostEqual(
            parsed_dt.timestamp(),
            expected_dt_approx.timestamp(),
            delta=timedelta(
                days=1
            ).total_seconds(),  # Allow for minor discrepancies if 'now' is very close to a day boundary
        )

    def test_parse_backfill_start_date_default_string_1_year_ago(self):
        now = datetime.now(timezone.utc)
        expected_dt_approx = now - timedelta(days=365)
        parsed_dt = ingestion_helpers.parse_backfill_start_date("1_year_ago")
        self.assertAlmostEqual(
            parsed_dt.timestamp(),
            expected_dt_approx.timestamp(),
            delta=timedelta(days=1).total_seconds(),
        )


if __name__ == "__main__":
    unittest.main()
