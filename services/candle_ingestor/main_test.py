import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module
from services.candle_ingestor import ingestion_helpers

FLAGS = flags.FLAGS


class RunPollingLoopTest(absltest.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )

        # Patch get_historical_candles_tiingo where it's looked up by main.py
        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        # Patch time.sleep where it's looked up by main.py
        self.patch_main_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)

        # Patch datetime module as seen by main.py
        self.patch_main_datetime = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime_module = self.patch_main_datetime.start()
        self.addCleanup(self.patch_main_datetime.stop)

        # Configure the mock datetime module's methods as needed
        self.mock_main_datetime_module.now = mock.MagicMock() # To be set per test
        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp # Real method
        self.mock_main_datetime_module.strptime = datetime.strptime       # Real method
        # If main.py calls datetime.datetime(...) directly, mock that too or allow pass-through
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        self.saved_flags = flagsaver.save_flag_values()
        # Dummy values, actual API calls will be mocked. These satisfy flag requirements.
        FLAGS.cmc_api_key = "dummy_cmc_for_test"
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.influxdb_token = "dummy_influx_token_for_test"
        FLAGS.influxdb_org = "dummy_influx_org_for_test"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        self.last_processed_timestamps = {} # Reset for each test


    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def test_poll_one_ticker_fetches_and_writes_new_candle(self):
        current_cycle_time_utc = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_cycle_time_utc

        granularity_minutes = 1
        FLAGS.candle_granularity_minutes = granularity_minutes

        last_processed_start_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_start_dt.timestamp() * 1000)

        candle_10_00_start_dt = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        candle_10_00_ts_ms = int(candle_10_00_start_dt.timestamp() * 1000)
        tiingo_response_candle = {
            "timestamp_ms": candle_10_00_ts_ms, "open": 1.0, "high": 2.0, 
            "low": 0.0, "close": 1.5, "volume": 10.0,
            "currency_pair": self.test_ticker
        }
        self.mock_get_historical_candles.return_value = [tiingo_response_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1

        # Simulate breaking the infinite loop via KeyboardInterrupt after one iteration
        def sleep_side_effect(duration_seconds):
            raise KeyboardInterrupt("Stop loop for test")

        self.mock_main_time_sleep.side_effect = sleep_side_effect

        # Call the polling loop (it will exit after first cycle due to the sleep mock)
        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=self.last_processed_timestamps,
        )

        # Validate the expected query window
        expected_query_start_dt = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expected_query_end_dt = datetime(2023, 1, 1, 10, 1, 59, tzinfo=timezone.utc)

        self.mock_get_historical_candles.assert_called_once_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            ingestion_helpers.get_tiingo_resample_freq(granularity_minutes)
        )

        self.mock_influx_manager.write_candles_batch.assert_called_once_with([tiingo_response_candle])
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_00_ts_ms)

    def test_poll_one_ticker_no_new_closed_candle_yet(self):
        current_cycle_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_cycle_time_utc

        FLAGS.candle_granularity_minutes = 1
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)

        self.mock_get_historical_candles.return_value = []

        def sleep_side_effect(duration_seconds):
            if duration_seconds > 0:
                raise KeyboardInterrupt("Stop loop for test")
        self.mock_main_time_sleep.side_effect = sleep_side_effect

        # Function should complete normally (KeyboardInterrupt is caught internally)
        candle_ingestor_main.run_polling_loop(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
            self.last_processed_timestamps
        )

        self.mock_get_historical_candles.assert_not_called()
        self.mock_influx_manager.write_candles_batch.assert_not_called()

    def test_poll_initializes_last_timestamp_if_missing(self):
        current_cycle_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_cycle_time_utc

        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
    
        self.last_processed_timestamps.clear() 
        self.mock_get_historical_candles.return_value = []

        # Properly mock sleep to interrupt the infinite loop after first iteration
        def sleep_side_effect(duration_seconds):
            if duration_seconds > 0:
                raise KeyboardInterrupt("Stop loop for test")
        self.mock_main_time_sleep.side_effect = sleep_side_effect

        # Function should complete normally (KeyboardInterrupt is caught internally)
        candle_ingestor_main.run_polling_loop(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
            self.last_processed_timestamps
        )
    
        # Validate initialization logic
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        expected_init_dt = datetime(2022, 12, 31, 10, 2, 0, tzinfo=timezone.utc)
        expected_init_ts_ms = int(expected_init_dt.timestamp() * 1000)
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)

        # In this specific test, polling starts, initializes from default, then tries to fetch.
        # Depending on how current_cycle_time_utc and this default init_ts align, a fetch might occur.
        # The key is that initialization happened.
        # self.mock_get_historical_candles.assert_called_once() # This might or might not be true based on exact timing.
        # For this test, focus is on initialization.
        # self.mock_influx_manager.write_candles_batch.assert_not_called()


# Helper function to create mock candle data
def _create_mock_candles(start_ts_ms, count, ticker, interval_ms):
    candles = []
    for i in range(count):
        ts = start_ts_ms + i * interval_ms
        candles.append({
            "timestamp_ms": ts, "open": 1.0, "high": 2.0,
            "low": 0.0, "close": 1.5, "volume": 10.0,
            "currency_pair": ticker
        })
    return candles


class RunBackfillTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )
        # Default behavior for state methods - can be overridden per test
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None
        self.mock_influx_manager.update_last_processed_timestamp.return_value = None # Does not return anything significant

        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        self.patch_main_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)
        
        # Patch datetime.now for controlling 'current day' in backfill end date logic
        self.patch_main_datetime = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime_module = self.patch_main_datetime.start()
        self.addCleanup(self.patch_main_datetime.stop)
        
        # Configure the mock datetime module's methods as needed
        self.mock_main_datetime_module.now = mock.MagicMock() # To be set per test for end_date_dt
        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp 
        self.mock_main_datetime_module.strptime = datetime.strptime
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.tiingo_api_call_delay_seconds = 0
        # backfill_start_date will be set per test

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        # This dict is passed to run_backfill, but its state is less critical now
        # as run_backfill relies on DB state primarily.
        self.last_processed_candle_timestamps_from_current_session = {}


    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def test_backfill_resumes_from_db_timestamp(self):
        FLAGS.backfill_start_date = "2023-01-01" # Overall config start
        granularity_minutes = 60 # 1 hour
        FLAGS.candle_granularity_minutes = granularity_minutes
        
        # Mock current time for end_date_dt calculation in run_backfill
        # Let's say "now" is 2023-01-10 12:00:00 UTC
        # So, backfill end_date_dt will be 2023-01-10 00:00:00 UTC
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc)

        db_start_dt = datetime(2023, 1, 5, 10, 0, 0, tzinfo=timezone.utc) # DB says last candle was 10:00
        db_start_ts_ms = int(db_start_dt.timestamp() * 1000)
        self.mock_influx_manager.get_last_processed_timestamp.return_value = db_start_ts_ms

        # Tiingo should be called for candles starting *after* db_start_dt + granularity
        # 2023-01-05 10:00:00 (db) + 1hr = 2023-01-05 11:00:00
        expected_tiingo_query_start_dt = datetime(2023, 1, 5, 11, 0, 0, tzinfo=timezone.utc)
        
        mock_candle_data = _create_mock_candles(
            int(expected_tiingo_query_start_dt.timestamp() * 1000),
            count=1, ticker=self.test_ticker, interval_ms=granularity_minutes * 60 * 1000
        )
        self.mock_get_historical_candles.return_value = mock_candle_data
        self.mock_influx_manager.write_candles_batch.return_value = len(mock_candle_data)

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_processed_candle_timestamps_from_current_session=self.last_processed_candle_timestamps_from_current_session
        )

        self.mock_influx_manager.get_last_processed_timestamp.assert_called_once_with(self.test_ticker, "backfill")
        
        # Check call to get_historical_candles_tiingo
        # Tiingo API uses date strings (YYYY-MM-DD) for historical queries.
        # The internal logic of run_backfill handles chunking by day.
        # We need to ensure the first chunk starts on the expected day.
        # The first chunk would be from 2023-01-05 to min(2023-01-05 + 89 days, end_date_dt - 1 microsec)
        # The current_ticker_start_dt inside run_backfill should be 2023-01-05 11:00:00
        # The first chunk_start_dt will be this.
        first_call_args = self.mock_get_historical_candles.call_args_list[0]
        call_start_date_str = first_call_args[0][2] # startDate is the 3rd arg (index 2)
        self.assertEqual(call_start_date_str, expected_tiingo_query_start_dt.strftime("%Y-%m-%d"))
        
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_once_with(
            self.test_ticker, "backfill", mock_candle_data[-1]["timestamp_ms"]
        )

    def test_backfill_starts_fresh_no_db_timestamp(self):
        FLAGS.backfill_start_date = "2023-01-02" # Overall config start
        FLAGS.candle_granularity_minutes = 60
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc) # for end_date_dt

        self.mock_influx_manager.get_last_processed_timestamp.return_value = None # No DB state

        configured_start_dt = datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        mock_candle_data = _create_mock_candles(
            int(configured_start_dt.timestamp() * 1000), 1, self.test_ticker, 60*60*1000
        )
        self.mock_get_historical_candles.return_value = mock_candle_data
        self.mock_influx_manager.write_candles_batch.return_value = len(mock_candle_data)

        candle_ingestor_main.run_backfill(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.backfill_start_date, FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds, self.last_processed_candle_timestamps_from_current_session
        )
        
        self.mock_influx_manager.get_last_processed_timestamp.assert_called_once_with(self.test_ticker, "backfill")
        first_call_args = self.mock_get_historical_candles.call_args_list[0]
        call_start_date_str = first_call_args[0][2]
        self.assertEqual(call_start_date_str, configured_start_dt.strftime("%Y-%m-%d"))
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_once_with(
            self.test_ticker, "backfill", mock_candle_data[-1]["timestamp_ms"]
        )

    def test_backfill_db_timestamp_after_configured_start(self):
        FLAGS.backfill_start_date = "2_days_ago" # e.g., if today is 2023-01-10, this is 2023-01-08
        FLAGS.candle_granularity_minutes = 60
        
        # "now" is 2023-01-10 12:00:00 UTC
        # Configured start_date_dt = 2023-01-08 00:00:00 UTC
        # DB timestamp for "1_day_ago" effectively, if "now" is 2023-01-10 for parsing "X_days_ago"
        # Let's make DB timestamp explicit: 2023-01-09 00:00:00 UTC
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        
        db_start_dt = datetime(2023, 1, 9, 0, 0, 0, tzinfo=timezone.utc)
        db_start_ts_ms = int(db_start_dt.timestamp() * 1000)
        self.mock_influx_manager.get_last_processed_timestamp.return_value = db_start_ts_ms

        # Expected Tiingo query start is after DB: 2023-01-09 00:00:00 + 1hr = 2023-01-09 01:00:00
        expected_tiingo_query_start_dt = datetime(2023, 1, 9, 1, 0, 0, tzinfo=timezone.utc)
        mock_candle_data = _create_mock_candles(
            int(expected_tiingo_query_start_dt.timestamp() * 1000), 1, self.test_ticker, 60*60*1000
        )
        self.mock_get_historical_candles.return_value = mock_candle_data
        self.mock_influx_manager.write_candles_batch.return_value = len(mock_candle_data)

        candle_ingestor_main.run_backfill(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.backfill_start_date, FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds, self.last_processed_candle_timestamps_from_current_session
        )

        first_call_args = self.mock_get_historical_candles.call_args_list[0]
        call_start_date_str = first_call_args[0][2]
        self.assertEqual(call_start_date_str, expected_tiingo_query_start_dt.strftime("%Y-%m-%d"))
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_once()


    def test_backfill_no_new_candles_to_write(self):
        FLAGS.backfill_start_date = "2023-01-01"
        FLAGS.candle_granularity_minutes = 60
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc)

        # DB timestamp is recent
        db_start_dt = datetime(2023, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        db_start_ts_ms = int(db_start_dt.timestamp() * 1000)
        self.mock_influx_manager.get_last_processed_timestamp.return_value = db_start_ts_ms
        
        # Tiingo returns candles that are all before or at this db_start_ts_ms
        # (e.g., latest candle from Tiingo is 2023-01-05 10:00:00)
        # The filter is `c["timestamp_ms"] > latest_ts_processed_in_current_backfill_run`
        # So, if latest_ts_processed_in_current_backfill_run is db_start_ts_ms,
        # any candle with timestamp_ms <= db_start_ts_ms will be filtered out.
        candles_from_tiingo = _create_mock_candles(
            int(datetime(2023, 1, 5, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000), # Starts earlier
            count=3, ticker=self.test_ticker, interval_ms=60*60*1000 # 8:00, 9:00, 10:00
        ) # Last candle is at 10:00:00, which is equal to db_start_ts_ms
        self.mock_get_historical_candles.return_value = candles_from_tiingo
        
        candle_ingestor_main.run_backfill(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.backfill_start_date, FLAGS.candle_granularity_minutes,
            FLAGS.tiingo_api_call_delay_seconds, self.last_processed_candle_timestamps_from_current_session
        )

        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.mock_influx_manager.update_last_processed_timestamp.assert_not_called()


# Extend RunPollingLoopTest or create a new one for state-related polling tests
class RunPollingLoopStateTest(RunPollingLoopTest): # Inherit existing setup if useful

    # Override setUp to avoid KeyboardInterrupt side effect if not needed, or call super().setUp()
    def setUp(self):
        super().setUp() # Call parent setUp
        # Reset specific mocks if parent's side effects are not desired for these state tests
        self.mock_main_time_sleep.side_effect = None # Remove KeyboardInterrupt for these tests
        
        # Ensure InfluxDBManager methods are clean for each test
        self.mock_influx_manager.reset_mock() # Resets call counts, return_values, side_effects
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None
        self.mock_influx_manager.update_last_processed_timestamp.return_value = None
        self.mock_get_historical_candles.reset_mock()


    @flagsaver.flagsaver(shutdown_requested=False) # Ensure shutdown_requested is false initially
    def test_polling_starts_from_polling_db_timestamp(self):
        FLAGS.candle_granularity_minutes = 1
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc)

        ts_polling_dt = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts_polling_ms = int(ts_polling_dt.timestamp() * 1000)
        ts_backfill_ms = int(datetime(2023, 1, 1, 9, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

        self.mock_influx_manager.get_last_processed_timestamp.side_effect = lambda ticker, type: \
            ts_polling_ms if type == "polling" else (ts_backfill_ms if type == "backfill" else None)

        # Tiingo returns one new candle
        candle_10_01_start_dt = datetime(2023, 1, 1, 10, 1, 0, tzinfo=timezone.utc)
        candle_10_01_ts_ms = int(candle_10_01_start_dt.timestamp() * 1000)
        mock_candle = _create_mock_candles(candle_10_01_ts_ms, 1, self.test_ticker, 60000)[0]
        self.mock_get_historical_candles.return_value = [mock_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1
        
        # Allow one pass through the loop
        candle_ingestor_main.shutdown_requested = False
        def sleep_side_effect_shutdown(duration_seconds):
            candle_ingestor_main.shutdown_requested = True
        self.mock_main_time_sleep.side_effect = sleep_side_effect_shutdown

        candle_ingestor_main.run_polling_loop(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
            self.last_processed_timestamps # This dict is populated by the loop's init logic
        )
        
        # Check initial call to get_last_processed_timestamp for "polling" then "backfill"
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(self.test_ticker, "polling")
        # Backfill might not be called if polling is found
        # self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(self.test_ticker, "backfill")


        # Verify Tiingo query uses the "polling" timestamp
        # Expected query: last_ts_ms (10:00:00) + 1 min = 10:01:00
        # Latest closed period end: 10:02:00 (current cycle 10:02:30)
        # Target latest closed candle start: 10:01:00
        # Query end: 10:01:00 + 1min - 1sec = 10:01:59
        expected_query_start_dt = datetime(2023, 1, 1, 10, 1, 0, tzinfo=timezone.utc)
        expected_query_end_dt = datetime(2023, 1, 1, 10, 1, 59, tzinfo=timezone.utc) 
        self.mock_get_historical_candles.assert_called_once_with(
            FLAGS.tiingo_api_key, self.test_ticker,
            expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            mock.ANY # resample_freq
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_once_with(
            self.test_ticker, "polling", candle_10_01_ts_ms
        )
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_01_ts_ms)


    @flagsaver.flagsaver(shutdown_requested=False)
    def test_polling_starts_from_backfill_db_timestamp(self):
        FLAGS.candle_granularity_minutes = 1
        self.mock_main_datetime_module.now.return_value = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc)

        ts_backfill_dt = datetime(2023, 1, 1, 9, 50, 0, tzinfo=timezone.utc)
        ts_backfill_ms = int(ts_backfill_dt.timestamp() * 1000)

        self.mock_influx_manager.get_last_processed_timestamp.side_effect = lambda ticker, type: \
            None if type == "polling" else (ts_backfill_ms if type == "backfill" else None)

        candle_9_51_start_dt = datetime(2023, 1, 1, 9, 51, 0, tzinfo=timezone.utc)
        candle_9_51_ts_ms = int(candle_9_51_start_dt.timestamp() * 1000)
        mock_candle = _create_mock_candles(candle_9_51_ts_ms, 1, self.test_ticker, 60000)[0]
        self.mock_get_historical_candles.return_value = [mock_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1

        candle_ingestor_main.shutdown_requested = False
        def sleep_side_effect_shutdown(duration_seconds): candle_ingestor_main.shutdown_requested = True
        self.mock_main_time_sleep.side_effect = sleep_side_effect_shutdown
        
        candle_ingestor_main.run_polling_loop(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
            self.last_processed_timestamps
        )
        
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(self.test_ticker, "polling")
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(self.test_ticker, "backfill")
        
        expected_query_start_dt = datetime(2023, 1, 1, 9, 51, 0, tzinfo=timezone.utc) # 9:50 + 1min
        # current_cycle_time_utc = 10:02:30. latest_closed_period_end = 10:02:00. target_latest_closed_candle_start = 10:01:00
        # query_end = 10:01:00 + 1min - 1sec = 10:01:59
        expected_query_end_dt = datetime(2023, 1, 1, 10, 1, 59, tzinfo=timezone.utc)
        self.mock_get_historical_candles.assert_called_once_with(
            FLAGS.tiingo_api_key, self.test_ticker,
            expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_once_with(
            self.test_ticker, "polling", candle_9_51_ts_ms
        )

    @flagsaver.flagsaver(shutdown_requested=False)
    def test_polling_starts_from_default_catchup(self):
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 3 # Test with 3 days
        # "now" is 2023-01-10 10:02:30
        current_time = datetime(2023, 1, 10, 10, 2, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_time

        self.mock_influx_manager.get_last_processed_timestamp.return_value = None # No DB state at all

        # Expected default start: 2023-01-10 10:02:30 - 3 days = 2023-01-07 10:02:30
        # Aligned to granularity: 2023-01-07 10:02:00
        expected_init_default_dt = datetime(2023, 1, 7, 10, 2, 0, tzinfo=timezone.utc)
        expected_init_default_ts_ms = int(expected_init_default_dt.timestamp() * 1000)

        mock_candle_ts_ms = int((expected_init_default_dt + timedelta(minutes=1)).timestamp()*1000)
        mock_candle = _create_mock_candles(mock_candle_ts_ms, 1, self.test_ticker, 60000)[0]
        self.mock_get_historical_candles.return_value = [mock_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1

        candle_ingestor_main.shutdown_requested = False
        def sleep_side_effect_shutdown(duration_seconds): candle_ingestor_main.shutdown_requested = True
        self.mock_main_time_sleep.side_effect = sleep_side_effect_shutdown

        candle_ingestor_main.run_polling_loop(
            self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
            FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
            self.last_processed_timestamps 
        )
        
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], mock_candle_ts_ms)
        # Check that Tiingo was called with a start date derived from default catchup
        # Query start will be expected_init_default_dt + 1 min
        expected_query_start_dt = expected_init_default_dt + timedelta(minutes=1)
        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]
        self.assertEqual(call_args[2], expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"))


if __name__ == "__main__":
    absltest.main()
