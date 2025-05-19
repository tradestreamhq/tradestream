import unittest
from unittest import mock # Corrected import for mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

# Modules to test or mock
# Import the main module we are testing functions from or whose functions we call
from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module
# We will mock functions from tiingo_client directly where they are called from main
from services.candle_ingestor import ingestion_helpers

FLAGS = flags.FLAGS


class RunPollingLoopTest(absltest.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )

        # Patch get_historical_candles_tiingo where it's used by candle_ingestor_main
        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo" # Path to where it's imported in main.py
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        # Patch time.sleep and datetime.now within the main module being tested
        self.patch_main_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)

        self.patch_main_datetime_now = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime = self.patch_main_datetime_now.start()
        self.addCleanup(self.patch_main_datetime_now.stop)


        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.tiingo_api_key = "dummy_tiingo_key_for_test_will_be_mocked" # Value doesn't matter due to mock
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0 # Default to 0 for most tests

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        self.last_processed_timestamps = {}

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def test_poll_one_ticker_fetches_and_writes_new_candle(self):
        # --- Arrange ---
        current_time_utc = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc) # 10:02:30
        self.mock_main_datetime.now.return_value = current_time_utc
        self.mock_main_datetime.fromtimestamp = datetime.fromtimestamp # Allow real fromtimestamp for other uses
        self.mock_main_datetime.strptime = datetime.strptime # Allow real strptime

        granularity_minutes = 1
        FLAGS.candle_granularity_minutes = granularity_minutes

        last_processed_start_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_start_dt.timestamp() * 1000)

        candle_10_00_ts_ms = int(datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        tiingo_response_candle = {
            "timestamp_ms": candle_10_00_ts_ms, "open": 1.0, "high": 2.0, "low": 0.0, "close": 1.5, "volume": 10.0,
            "currency_pair": self.test_ticker
        }
        self.mock_get_historical_candles.return_value = [tiingo_response_candle]
        self.mock_influx_manager.write_candles_batch.return_value = 1

        # Make the main loop's sleep raise KeyboardInterrupt to exit after one cycle
        self.mock_main_time_sleep.side_effect = \
            lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop for test")) if t > 1 else None


        # --- Act & Assert ---
        with self.assertRaises(KeyboardInterrupt): # Expected due to mock_main_time_sleep
            candle_ingestor_main.run_polling_loop(
                influx_manager=self.mock_influx_manager,
                tiingo_tickers=self.tiingo_tickers,
                tiingo_api_key=FLAGS.tiingo_api_key,
                candle_granularity_minutes=granularity_minutes,
                api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds, # Will be 0
                initial_catchup_days=FLAGS.polling_initial_catchup_days,
                last_processed_timestamps=self.last_processed_timestamps,
            )

        # --- Assert ---
        expected_query_start_dt_str = (last_processed_start_dt + timedelta(minutes=granularity_minutes)).strftime("%Y-%m-%dT%H:%M:%S")
        # Target candle starts at 10:01, so query ends at 10:01:59
        # Corrected: target candle is 10:00. Polling for 10:00:00 to 10:00:59
        target_candle_start_dt = datetime(2023,1,1,10,0,0, tzinfo=timezone.utc)
        expected_query_end_dt_str = (target_candle_start_dt + timedelta(minutes=granularity_minutes) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")


        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]
        self.assertEqual(call_args[1], self.test_ticker)
        self.assertEqual(call_args[2], expected_query_start_dt_str) # startDate
        self.assertEqual(call_args[3], expected_query_end_dt_str)   # endDate
        self.assertEqual(call_args[4], ingestion_helpers.get_tiingo_resample_freq(granularity_minutes))

        self.mock_influx_manager.write_candles_batch.assert_called_once_with([tiingo_response_candle])
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_00_ts_ms)
        
        # Check that the main loop sleep was attempted (and then interrupted)
        self.mock_main_time_sleep.assert_called()


    def test_poll_one_ticker_no_new_closed_candle_yet(self):
        # --- Arrange ---
        current_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc) # 10:00:30
        self.mock_main_datetime.now.return_value = current_time_utc
        self.mock_main_datetime.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime.strptime = datetime.strptime


        FLAGS.candle_granularity_minutes = 1
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc) # Last candle was 09:59
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)
        
        self.mock_get_historical_candles.return_value = []

        # Make the main loop's sleep raise KeyboardInterrupt
        self.mock_main_time_sleep.side_effect = \
            lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop for test")) if t > 1 else None

        # --- Act & Assert ---
        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        # Should try to fetch the 10:00 candle, but it's not closed yet by current_time_utc
        # The filtering logic inside run_polling_loop should handle this.
        # Or, the query itself might be for the 09:59 - 10:00 candle if last_ts is 09:59
        # Let's trace the logic in run_polling_loop:
        # target_candle_start_dt_utc (most recent closed) would be 09:59
        # if last_ts_ms is 09:59, it will skip. This test needs adjustment.

        # If last processed was 09:59, target will be 09:59. So it will skip. This is correct.
        self.mock_get_historical_candles.assert_not_called() # Because target candle (09:59) <= last_ts_ms (09:59)
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], int(last_processed_dt.timestamp() * 1000))


    def test_poll_initializes_last_timestamp_if_missing(self):
        # --- Arrange ---
        current_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        self.mock_main_datetime.now.return_value = current_time_utc
        self.mock_main_datetime.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime.strptime = datetime.strptime

        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        
        self.last_processed_timestamps.clear() 
        self.mock_get_historical_candles.return_value = []

        self.mock_main_time_sleep.side_effect = \
            lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop for test")) if t > 1 else None

        # --- Act & Assert ---
        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        expected_init_ts_ms = int((current_time_utc - timedelta(days=1)).timestamp() * 1000)
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)
        
        # It should try to fetch from this initialized catchup time
        self.mock_get_historical_candles.assert_called_once()
        self.mock_influx_manager.write_candles_batch.assert_not_called()

if __name__ == "__main__":
    absltest.main()
