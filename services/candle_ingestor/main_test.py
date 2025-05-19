import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module
# We will mock functions FROM tiingo_client where they are used IN main
# from services.candle_ingestor import tiingo_client as tiingo_client_module # Not needed if mocking main's usage
from services.candle_ingestor import ingestion_helpers

FLAGS = flags.FLAGS


class RunPollingLoopTest(absltest.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )

        # Patch get_historical_candles_tiingo as it's called from candle_ingestor_main
        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        # Patch time.sleep within candle_ingestor_main
        self.patch_main_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)

        # Patch datetime.now within candle_ingestor_main
        self.patch_main_datetime = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime_object = self.patch_main_datetime.start() # This mocks the datetime module
        self.addCleanup(self.patch_main_datetime.stop)

        # Ensure that methods like strftime and fromtimestamp still work on datetime objects
        # by delegating to the real datetime object for those.
        self.mock_main_datetime_object.strptime = datetime.strptime
        self.mock_main_datetime_object.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime_object.now = mock.MagicMock() # This specific method is what we'll control

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc" # Required by main's flag check, but not used in these tests
        FLAGS.tiingo_api_key = "dummy_tiingo_key_for_test_mocked"
        FLAGS.influxdb_token = "dummy_token" # Required
        FLAGS.influxdb_org = "dummy_org"     # Required
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        # Reset for each test
        self.last_processed_timestamps = {}


    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def test_poll_one_ticker_fetches_and_writes_new_candle(self):
        current_time_utc = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_object.now.return_value = current_time_utc
        # For datetime.fromtimestamp used internally by parsing logic if any (e.g. in _parse_tiingo_timestamp)
        self.mock_main_datetime_object.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


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

        # Make the main loop's sleep (at the end of the while True) raise KeyboardInterrupt
        def sleep_side_effect(duration_seconds):
            if duration_seconds > 1: # Target the main loop sleep, not the 0s inter-ticker sleep
                raise KeyboardInterrupt("Stop loop for test")
        self.mock_main_time_sleep.side_effect = sleep_side_effect

        with self.assertRaises(KeyboardInterrupt):
            candle_ingestor_main.run_polling_loop(
                influx_manager=self.mock_influx_manager,
                tiingo_tickers=self.tiingo_tickers,
                tiingo_api_key=FLAGS.tiingo_api_key,
                candle_granularity_minutes=granularity_minutes,
                api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
                initial_catchup_days=FLAGS.polling_initial_catchup_days,
                last_processed_timestamps=self.last_processed_timestamps,
            )
        
        # Expected polling window for Tiingo (to fetch 10:00:00 - 10:00:59 candle)
        # Query start is after the last processed candle (09:59:00 + 1min = 10:00:00)
        expected_query_start_dt = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        # Query end is the end of that target candle's interval
        expected_query_end_dt = datetime(2023, 1, 1, 10, 0, 59, tzinfo=timezone.utc)


        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]

        self.assertEqual(call_args[1], self.test_ticker)
        self.assertEqual(call_args[2], expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(call_args[3], expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(call_args[4], ingestion_helpers.get_tiingo_resample_freq(granularity_minutes))

        self.mock_influx_manager.write_candles_batch.assert_called_once_with([tiingo_response_candle])
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_00_ts_ms)
        self.mock_main_time_sleep.assert_called() # Ensure sleep was attempted

    def test_poll_one_ticker_no_new_closed_candle_yet(self):
        current_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc) # 10:00:30
        self.mock_main_datetime_object.now.return_value = current_time_utc
        self.mock_main_datetime_object.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        FLAGS.candle_granularity_minutes = 1
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)
        
        self.mock_get_historical_candles.return_value = []

        self.mock_main_time_sleep.side_effect = lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop")) if t > 1 else None

        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        # In this scenario (current time 10:00:30, last processed 09:59 candle),
        # the target_candle_start_dt_utc becomes 09:59:00.
        # The condition `target_candle_start_dt_utc.timestamp() * 1000 <= last_ts_ms` will be true.
        # So, `get_historical_candles` should NOT be called.
        self.mock_get_historical_candles.assert_not_called()
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], int(last_processed_dt.timestamp() * 1000))

    def test_poll_initializes_last_timestamp_if_missing(self):
        current_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        self.mock_main_datetime_object.now.return_value = current_time_utc
        self.mock_main_datetime_object.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        
        self.last_processed_timestamps.clear() 
        self.mock_get_historical_candles.return_value = []

        self.mock_main_time_sleep.side_effect = lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop")) if t > 1 else None

        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        expected_init_ts_ms = int((current_time_utc - timedelta(days=FLAGS.polling_initial_catchup_days)).timestamp() * 1000)
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)
        
        self.mock_get_historical_candles.assert_called_once() # Should be called for the catch-up period
        self.mock_influx_manager.write_candles_batch.assert_not_called()


if __name__ == "__main__":
    absltest.main()
