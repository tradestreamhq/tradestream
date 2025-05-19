import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

# Modules to test or mock
from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module
from services.candle_ingestor import tiingo_client as tiingo_client_module
from services.candle_ingestor import ingestion_helpers

# Make sure FLAGS are accessible
FLAGS = flags.FLAGS


class RunPollingLoopTest(absltest.TestCase): # Using absltest.TestCase for flagsaver

    def setUp(self):
        super().setUp()
        # Mock dependencies that are globally initialized or passed around
        self.mock_influx_manager = mock.MagicMock(spec=influx_client_module.InfluxDBManager)
        self.mock_get_historical_candles = mock.patch.object(
            tiingo_client_module, "get_historical_candles_tiingo"
        ).start()
        self.addCleanup(mock.patch.stopall) # Stops all patches started with start()

        # Default flag values for tests
        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.tiingo_api_key = "fake_tiingo_key"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1 # Small catchup for tests
        FLAGS.tiingo_api_call_delay_seconds = 0 # No delay in tests

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        self.last_processed_timestamps = {}


    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    @mock.patch("services.candle_ingestor.main.datetime")
    @mock.patch("services.candle_ingestor.main.time")
    def test_poll_one_ticker_fetches_and_writes_new_candle(
        self, mock_time, mock_datetime
    ):
        # --- Arrange ---
        current_time_utc = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc) # 10:02:30
        mock_datetime.now.return_value = current_time_utc
        mock_datetime.fromtimestamp = datetime.fromtimestamp # Allow real fromtimestamp
        mock_time.monotonic.return_value = 1.0 # For loop duration calculation
        mock_time.sleep.return_value = None # Don't actually sleep

        granularity_minutes = 1
        FLAGS.candle_granularity_minutes = granularity_minutes

        # Last processed candle was for 09:59:00, so its timestamp is 09:59:00
        last_processed_start_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_start_dt.timestamp() * 1000)

        # Expected polling window for Tiingo (to fetch 10:00:00 - 10:01:00 candle, which closed at 10:01:00)
        # Target candle is 10:00 - 10:01
        # Current time 10:02:30. Most recent closed candle period start: 10:01:00.
        # We need to query from just after the last processed candle (09:59:00 + 1min = 10:00:00)
        # up to the end of the target candle (10:01:00 - 1sec)
        
        # Tiingo response: one candle for 10:00:00
        candle_10_00_ts_ms = int(datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        tiingo_response_candle = {
            "timestamp_ms": candle_10_00_ts_ms, "open": 1, "high": 2, "low": 0, "close": 1.5, "volume": 10,
            "currency_pair": self.test_ticker
        }
        self.mock_get_historical_candles.return_value = [tiingo_response_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1 # 1 candle written

        # --- Act ---
        # We need to call the main loop and break it after one iteration for testing
        # This is tricky with `while True`. A refactor of `run_polling_loop` to process
        # one cycle would be better. For now, we'll mock `time.sleep` to raise an exception
        # to break the loop after the first pass.
        mock_time.sleep.side_effect = KeyboardInterrupt("Stop loop for test")

        with self.assertRaises(KeyboardInterrupt): # Expected due to mock_time.sleep
            candle_ingestor_main.run_polling_loop(
                influx_manager=self.mock_influx_manager,
                tiingo_tickers=self.tiingo_tickers,
                tiingo_api_key=FLAGS.tiingo_api_key,
                candle_granularity_minutes=granularity_minutes,
                api_call_delay_seconds=0,
                initial_catchup_days=FLAGS.polling_initial_catchup_days,
                last_processed_timestamps=self.last_processed_timestamps,
            )

        # --- Assert ---
        # Verify get_historical_candles_tiingo was called with correct params
        # Start date for query: after last processed candle (09:59 + 1min = 10:00)
        expected_query_start_dt = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        # End date for query: target candle start + granularity - 1s (end of 10:00 candle is 10:00:59)
        expected_query_end_dt = datetime(2023, 1, 1, 10, 0, 59, tzinfo=timezone.utc)

        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]
        self.assertEqual(call_args[1], self.test_ticker) # ticker
        self.assertEqual(call_args[2], expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S")) # startDate
        self.assertEqual(call_args[3], expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S")) # endDate
        self.assertEqual(call_args[4], ingestion_helpers.get_tiingo_resample_freq(granularity_minutes)) # resampleFreq

        # Verify InfluxDB write
        self.mock_influx_manager.write_candles_batch.assert_called_once_with([tiingo_response_candle])

        # Verify last_processed_timestamps updated
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_00_ts_ms)

    @mock.patch("services.candle_ingestor.main.datetime")
    @mock.patch("services.candle_ingestor.main.time")
    def test_poll_one_ticker_no_new_closed_candle_yet(
        self, mock_time, mock_datetime
    ):
        # --- Arrange ---
        # Current time is 10:00:30. Granularity 1 min.
        # Last closed candle period was 09:59:00 - 10:00:00.
        # The current candle period 10:00:00 - 10:01:00 hasn't closed yet.
        current_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
        mock_datetime.now.return_value = current_time_utc
        mock_datetime.fromtimestamp = datetime.fromtimestamp
        mock_time.monotonic.return_value = 1.0
        mock_time.sleep.side_effect = KeyboardInterrupt("Stop loop")

        FLAGS.candle_granularity_minutes = 1
        # Last processed candle was for 09:59:00
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)
        
        self.mock_get_historical_candles.return_value = [] # Tiingo returns no *new closed* candles

        # --- Act & Assert ---
        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        # get_historical_candles_tiingo should still be called to check for the 09:59-10:00 candle.
        # Target candle to check for is 09:59:00 - 10:00:00 (which is last_processed_dt)
        # Polling logic might try to fetch the *next* one, which is 10:00:00.
        # If current time is 10:00:30, the 10:00:00-10:01:00 candle is NOT YET CLOSED.
        # The logic in run_polling_loop should filter out candles whose period hasn't closed.
        # In this setup, it might try to fetch for 10:00:00, which is fine.
        # The key is that write_candles_batch is not called if no *new, closed* candles are found.

        # Based on the current `run_polling_loop` logic:
        # target_candle_start_dt_utc will be 10:00:00
        # query_start_date_str will be (09:59:00 + 1min).strftime = "2023-01-01T10:00:00"
        # query_end_for_api will be (10:00:00 + 1min - 1s).strftime = "2023-01-01T10:00:59"
        # If get_historical_candles returns [], no write should happen.
        self.mock_get_historical_candles.assert_called_once()
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], int(last_processed_dt.timestamp() * 1000))


    @mock.patch("services.candle_ingestor.main.datetime")
    @mock.patch("services.candle_ingestor.main.time")
    def test_poll_initializes_last_timestamp_if_missing(
        self, mock_time, mock_datetime
    ):
        # --- Arrange ---
        current_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = current_time_utc
        mock_datetime.fromtimestamp = datetime.fromtimestamp
        mock_time.monotonic.return_value = 1.0
        mock_time.sleep.side_effect = KeyboardInterrupt("Stop loop")

        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        
        # last_processed_timestamps is empty for self.test_ticker
        self.last_processed_timestamps.clear() 
        
        self.mock_get_historical_candles.return_value = [] # No new candles found in catchup

        # --- Act & Assert ---
        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps # Pass the empty map
            )
        
        # Verify that last_processed_timestamps gets initialized for the ticker
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        expected_init_ts_ms = int((current_time_utc - timedelta(days=1)).timestamp() * 1000)
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)
        
        # Verify get_historical_candles was called for the catch-up period
        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]
        # query_start_date_str should be roughly 'initial_catchup_days' ago from current_time_utc
        # query_end_date_str should be for the most recent closed candle before current_time_utc
        self.mock_influx_manager.write_candles_batch.assert_not_called()

    # TODO: Add more tests:
    # - Tiingo API error during polling.
    # - InfluxDB write error during polling.
    # - Multiple tickers in the loop.
    # - Loop timing and sleep calculation (more involved, might need to mock time.monotonic differently for multiple calls).


if __name__ == "__main__":
    absltest.main()
