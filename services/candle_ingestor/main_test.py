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
        current_cycle_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc) # 10:00:30
        self.mock_main_datetime_module.now.return_value = current_cycle_time_utc

        FLAGS.candle_granularity_minutes = 1
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)
        
        self.mock_get_historical_candles.return_value = []
        self.mock_main_time_sleep.side_effect = KeyboardInterrupt("Stop loop")

        with self.assertRaises(KeyboardInterrupt):
            candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        # Logic in main.py: target_latest_closed_candle_start_dt_utc is 09:59.
        # Since this <= last_ts_ms (09:59), API should not be called.
        self.mock_get_historical_candles.assert_not_called()
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], int(last_processed_dt.timestamp() * 1000))
        self.mock_main_time_sleep.assert_called_once() # Inter-ticker delay (0s) + main loop sleep (interrupted)


    def test_poll_initializes_last_timestamp_if_missing(self):
        current_cycle_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_cycle_time_utc # For now_utc_for_init and current_cycle_time_utc

        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        
        self.last_processed_timestamps.clear() 
        self.mock_get_historical_candles.return_value = []
        self.mock_main_time_sleep.side_effect = KeyboardInterrupt("Stop loop")

        with self.assertRaises(KeyboardInterrupt):
            candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        # now_utc_for_init will be 10:02:00. catchup_days=1.
        # default_catchup_start_dt = 2023-01-01T10:02:00 - 1 day = 2022-12-31T10:02:00
        # default_catchup_start_minute = (2 // 1) * 1 = 2
        # default_catchup_start_dt_aligned = 2022-12-31T10:02:00
        expected_init_dt_aligned = current_cycle_time_utc - timedelta(days=FLAGS.polling_initial_catchup_days)
        expected_init_minute_floored = (expected_init_dt_aligned.minute // FLAGS.candle_granularity_minutes) * FLAGS.candle_granularity_minutes
        expected_init_dt_aligned = expected_init_dt_aligned.replace(minute=expected_init_minute_floored, second=0, microsecond=0)
        expected_init_ts_ms = int(expected_init_dt_aligned.timestamp() * 1000)
        
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)
        
        self.mock_get_historical_candles.assert_called_once() # Called for the catch-up period
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.mock_main_time_sleep.assert_called() # Inter-ticker (0s) + main loop sleep (interrupted)

if __name__ == "__main__":
    absltest.main()
