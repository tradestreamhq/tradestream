import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module

FLAGS = flags.FLAGS


class BaseIngestorTest(absltest.TestCase):
    def setUp(self):
        super().setUp()

        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )
        self.mock_influx_manager.get_client.return_value = (
            self.mock_influx_manager
        )  # Simulate connected client
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None
        self.mock_influx_manager.update_last_processed_timestamp.return_value = None
        self.mock_influx_manager.write_candles_batch.return_value = (
            1  # Assume 1 batch written
        )

        self.patch_influx_db_manager = mock.patch(
            "services.candle_ingestor.main.InfluxDBManager",
            return_value=self.mock_influx_manager,
        )
        self.mock_influx_db_manager_class = self.patch_influx_db_manager.start()
        self.addCleanup(self.patch_influx_db_manager.stop)

        self.patch_get_top_n_crypto_symbols = mock.patch(
            "services.candle_ingestor.main.get_top_n_crypto_symbols"
        )
        self.mock_get_top_n_crypto_symbols = self.patch_get_top_n_crypto_symbols.start()
        self.addCleanup(self.patch_get_top_n_crypto_symbols.stop)

        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        # Mock time.sleep to prevent actual sleeping during tests
        self.patch_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_time_sleep = self.patch_time_sleep.start()
        self.addCleanup(self.patch_time_sleep.stop)

        # Mock datetime.now for controllable time
        self.patch_main_datetime_now = mock.patch(
            "services.candle_ingestor.main.datetime"
        )
        self.mock_main_datetime_module = self.patch_main_datetime_now.start()
        self.addCleanup(self.patch_main_datetime_now.stop)

        # Also mock datetime in ingestion_helpers if it's used there directly for 'now'
        self.patch_helpers_datetime_now = mock.patch(
            "services.candle_ingestor.ingestion_helpers.datetime"
        )
        self.mock_helpers_datetime_module = self.patch_helpers_datetime_now.start()
        self.addCleanup(self.patch_helpers_datetime_now.stop)

        # Configure the datetime mock to behave like the real datetime for non-now calls
        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime_module.strptime = datetime.strptime
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(
            *args, **kwargs
        )
        self.mock_main_datetime_module.timezone = (
            timezone  # Allow access to timezone.utc
        )

        self.mock_helpers_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_helpers_datetime_module.strptime = datetime.strptime
        self.mock_helpers_datetime_module.side_effect = (
            lambda *args, **kwargs: datetime(*args, **kwargs)
        )
        self.mock_helpers_datetime_module.timezone = timezone

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc_for_test"
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.influxdb_token = "dummy_influx_token_for_test"
        FLAGS.influxdb_org = "dummy_influx_org_for_test"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.catch_up_initial_days = 1  # Default for tests if not overridden
        FLAGS.tiingo_api_call_delay_seconds = 0  # No delay in tests
        FLAGS.backfill_start_date = "1_day_ago"  # Default for tests

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [
            self.test_ticker,
            "ethusd",
        ]  # Include multiple for some tests
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        self.last_processed_timestamps_shared_state = {}

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def _set_current_time(self, dt_str_utc):
        """Sets the mock 'current time' for datetime.now(timezone.utc) calls."""
        mock_dt = datetime.fromisoformat(dt_str_utc).replace(tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = mock_dt
        self.mock_helpers_datetime_module.now.return_value = mock_dt

    def _create_dummy_candle(self, timestamp_ms, pair="btcusd", close_price=100.0):
        return {
            "timestamp_ms": int(timestamp_ms),
            "open": close_price - 1,
            "high": close_price + 1,
            "low": close_price - 2,
            "close": close_price,
            "volume": 10.0,
            "currency_pair": pair,
        }


class RunBackfillTest(BaseIngestorTest):
    def test_backfill_new_ticker_no_db_state(self):
        """Test backfill starts from flag date when no DB state exists."""
        self._set_current_time(
            "2023-01-10T12:00:00"
        )  # Set current time for end_date_dt calculation
        FLAGS.backfill_start_date = "1_day_ago"  # Expected start: 2023-01-09T00:00:00Z (aligned by parse_backfill_start_date)
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        # Backfill runs up to the start of the current day
        expected_candle_ts_for_fetch_start = (
            datetime(2023, 1, 9, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        dummy_candle = self._create_dummy_candle(expected_candle_ts_for_fetch_start)
        self.mock_get_historical_candles.return_value = [dummy_candle]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=[
                self.test_ticker
            ],  # Test with a single ticker for simplicity here
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
        )
        # Start date for Tiingo is YYYY-MM-DD
        # End date is one day before current time's date (exclusive)
        # Current time is 2023-01-10, so backfill ends before 2023-01-10
        # For 1_day_ago from 2023-01-10, parse_backfill_start_date gives 2023-01-09T12:00:00Z
        # Backfill window: 2023-01-09 to 2023-01-09 (since end_date_dt is 2023-01-10T00:00:00Z)
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", "2023-01-09", mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle["timestamp_ms"]
        )
        self.assertEqual(
            self.last_processed_timestamps_shared_state[self.test_ticker],
            dummy_candle["timestamp_ms"],
        )

    def test_backfill_resumes_from_db_state(self):
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = (
            "5_days_ago"  # Earliest possible: 2023-01-05T12:00:00Z
        )
        db_resume_timestamp_ms = int(
            datetime(2023, 1, 7, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )  # DB state: 2023-01-07T00:00:00Z
        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            db_resume_timestamp_ms
        )

        # Expected fetch start for Tiingo: day after last processed + granularity alignment
        # last processed dt = 2023-01-07T00:00:00Z. Next period starts 2023-01-07T00:01:00Z
        # Tiingo API uses date strings. Effective start: 2023-01-07
        expected_candle_ts_for_fetch = (
            datetime(2023, 1, 7, 0, 1, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        dummy_candle_resumed = self._create_dummy_candle(expected_candle_ts_for_fetch)
        self.mock_get_historical_candles.return_value = [dummy_candle_resumed]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
        )
        # Backfill window: From 2023-01-07 up to (but not including) 2023-01-10
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-07", "2023-01-09", mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle_resumed["timestamp_ms"]
        )


class RunCatchUpTest(BaseIngestorTest):
    def test_catch_up_from_backfill_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        backfill_state_ms = int(
            datetime(2023, 1, 10, 11, 58, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.last_processed_timestamps_shared_state[
            self.test_ticker
        ] = backfill_state_ms
        # No "catch_up" state in DB, so it will use the backfill state from memory
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        # Expected fetch for catch-up: from 2023-01-10T11:59:00Z up to 2023-01-10T12:05:00Z
        expected_catch_up_candle_ts = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(expected_catch_up_candle_ts)
        self.mock_get_historical_candles.return_value = [polled_candle]

        candle_ingestor_main.run_catch_up(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T11:59:00",  # Start of next period after backfill
            "2023-01-10T12:05:00",  # Current time
            mock.ANY,
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "catch_up", polled_candle["timestamp_ms"]
        )
        self.assertEqual(
            self.last_processed_timestamps_shared_state[self.test_ticker],
            polled_candle["timestamp_ms"],
        )

    def test_catch_up_from_db_catch_up_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        # No in-memory state for this ticker initially
        catch_up_db_state_ms = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda ticker, type: (catch_up_db_state_ms if type == "catch_up" else None)
        )

        expected_catch_up_candle_ts = int(
            datetime(2023, 1, 10, 12, 1, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(expected_catch_up_candle_ts)
        self.mock_get_historical_candles.return_value = [polled_candle]

        candle_ingestor_main.run_catch_up(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,  # Initially empty for this ticker
            run_mode="wet",
        )
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "catch_up"
        )
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T12:01:00",  # Start of next period after DB catch_up state
            "2023-01-10T12:05:00",  # Current time
            mock.ANY,
        )


class MainFunctionTest(BaseIngestorTest):
    @flagsaver.flagsaver(backfill_start_date="skip", run_mode="dry")
    def test_main_dry_run_skip_backfill_runs_catch_up(self):
        self._set_current_time(
            "2023-01-02T00:00:00"
        )  # For deterministic catch-up start in dry run
        # Dry run uses fixed dummy tickers
        dummy_tickers = ["btcusd-dry", "ethusd-dry"]
        self.mock_get_top_n_crypto_symbols.return_value = dummy_tickers

        # Mock get_historical_candles for the catch-up part of the dry run
        # It will be called once per dummy ticker for catch-up
        def dry_run_catchup_candles(
            api_key, ticker, start_date_str, end_date_str, resample_freq
        ):
            # Simulate fetching one candle for the catch-up period
            # Convert start_date_str (which is YYYY-MM-DDTHH:MM:SS for intraday) to ms
            start_dt_for_dummy_candle = datetime.strptime(
                start_date_str, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=timezone.utc)
            return [
                self._create_dummy_candle(
                    start_dt_for_dummy_candle.timestamp() * 1000, pair=ticker
                )
            ]

        self.mock_get_historical_candles.side_effect = dry_run_catchup_candles

        with mock.patch.object(sys, "exit") as mock_exit:
            candle_ingestor_main.main(None)
            mock_exit.assert_called_once_with(0)  # Expect successful exit

        # run_backfill should not have called Tiingo API because it's skipped
        # run_catch_up should have simulated calls for its dummy tickers
        # It's hard to assert on the mock_get_historical_candles calls directly for backfill vs catchup
        # due to how dry run combines them. Instead, we check that it was called for catchup phase.
        self.assertEqual(
            self.mock_get_historical_candles.call_count, len(dummy_tickers)
        )  # Once per ticker for catch-up

    @flagsaver.flagsaver(run_mode="wet")
    def test_main_wet_run_executes_backfill_and_catch_up(self):
        self._set_current_time("2023-01-03T00:00:00")  # Day 3 for backfill and catchup
        FLAGS.backfill_start_date = "2_days_ago"  # Backfill 2023-01-01
        FLAGS.catch_up_initial_days = 1  # Catch up from 2023-01-02 if no state

        # Mock CMC
        self.mock_get_top_n_crypto_symbols.return_value = [self.test_ticker]

        # Mock InfluxDB state reads
        # For backfill, assume no prior state
        # For catch_up, also assume no prior "catch_up" state, will use backfill's result
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        # Mock Tiingo API responses
        # First call for backfill (e.g., 2023-01-01)
        backfill_candle_ts = int(
            datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        backfill_candles_response = [
            self._create_dummy_candle(backfill_candle_ts, pair=self.test_ticker)
        ]

        # Second call for catch-up (e.g., from 2023-01-01T10:01:00 up to 2023-01-03T00:00:00)
        catch_up_candle_ts = int(
            datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        catch_up_candles_response = [
            self._create_dummy_candle(
                catch_up_candle_ts, pair=self.test_ticker, close_price=110
            )
        ]

        self.mock_get_historical_candles.side_effect = [
            backfill_candles_response,  # For run_backfill
            catch_up_candles_response,  # For run_catch_up
        ]

        with mock.patch.object(sys, "exit") as mock_exit:
            candle_ingestor_main.main(None)
            mock_exit.assert_called_once_with(0)

        self.assertEqual(self.mock_get_historical_candles.call_count, 2)
        # Check backfill call
        self.mock_get_historical_candles.assert_any_call(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-01", "2023-01-02", mock.ANY
        )
        # Check catch-up call (starts after backfill_candle_ts)
        self.mock_get_historical_candles.assert_any_call(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-01T10:01:00",
            "2023-01-03T00:00:00",
            mock.ANY,
        )

        # Verify InfluxDB writes
        self.mock_influx_manager.write_candles_batch.assert_any_call(
            backfill_candles_response
        )
        self.mock_influx_manager.write_candles_batch.assert_any_call(
            catch_up_candles_response
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_any_call(
            self.test_ticker, "backfill", backfill_candle_ts
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_any_call(
            self.test_ticker, "catch_up", catch_up_candle_ts
        )


if __name__ == "__main__":
    absltest.main()
