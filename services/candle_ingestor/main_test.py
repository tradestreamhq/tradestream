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

        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        self.patch_main_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)

        self.patch_main_datetime = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime_module = self.patch_main_datetime.start()
        self.addCleanup(self.patch_main_datetime.stop)
        
        # Configure the mock datetime module
        self.mock_main_datetime_module.now = mock.MagicMock() # This will be set per test
        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime_module.strptime = datetime.strptime
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc"
        FLAGS.tiingo_api_key = "dummy_tiingo_key_for_test_mocked"
        FLAGS.influxdb_token = "dummy_token"
        FLAGS.influxdb_org = "dummy_org"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0 # Explicitly 0 for tests

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker] # Test with one ticker to simplify loop exit
        self.last_processed_timestamps = {}

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def test_poll_one_ticker_fetches_and_writes_new_candle(self):
        current_time_utc = datetime(2023, 1, 1, 10, 2, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_time_utc

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

        # Make the *main loop's* sleep (at the end of the while True) raise KeyboardInterrupt.
        # The inter-ticker sleep (FLAGS.tiingo_api_call_delay_seconds) is 0 so it won't be called with > 0.
        def sleep_side_effect(duration_seconds):
            # This will be called for the main loop's sleep_time
            # For other sleeps (e.g. api_call_delay_seconds if it were >0), it would just pass.
            if duration_seconds >= (FLAGS.candle_granularity_minutes * 60 * 0.5): # Heuristic for main loop sleep
                 raise KeyboardInterrupt("Stop loop for test after one main cycle")
            # else: pass # for very short sleeps like inter-ticker delay if it were non-zero
        self.mock_main_time_sleep.side_effect = sleep_side_effect


        with self.assertRaises(KeyboardInterrupt):
            candle_ingestor_main.run_polling_loop(
                influx_manager=self.mock_influx_manager,
                tiingo_tickers=self.tiingo_tickers, # Using single ticker list
                tiingo_api_key=FLAGS.tiingo_api_key,
                candle_granularity_minutes=granularity_minutes,
                api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
                initial_catchup_days=FLAGS.polling_initial_catchup_days,
                last_processed_timestamps=self.last_processed_timestamps,
            )
        
        expected_query_start_dt = last_processed_start_dt + timedelta(minutes=granularity_minutes)
        expected_query_end_dt = target_candle_start_dt = datetime(2023,1,1,10,0,0, tzinfo=timezone.utc) + timedelta(minutes=granularity_minutes) - timedelta(seconds=1)

        self.mock_get_historical_candles.assert_called_once()
        call_args = self.mock_get_historical_candles.call_args[0]
        self.assertEqual(call_args[1], self.test_ticker)
        self.assertEqual(call_args[2], expected_query_start_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(call_args[3], expected_query_end_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        self.assertEqual(call_args[4], ingestion_helpers.get_tiingo_resample_freq(granularity_minutes))

        self.mock_influx_manager.write_candles_batch.assert_called_once_with([tiingo_response_candle])
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], candle_10_00_ts_ms)
        self.mock_main_time_sleep.assert_called()


    def test_poll_one_ticker_no_new_closed_candle_yet(self):
        current_time_utc = datetime(2023, 1, 1, 10, 0, 30, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_time_utc
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


        FLAGS.candle_granularity_minutes = 1
        last_processed_dt = datetime(2023, 1, 1, 9, 59, 0, tzinfo=timezone.utc)
        self.last_processed_timestamps[self.test_ticker] = int(last_processed_dt.timestamp() * 1000)
        
        self.mock_get_historical_candles.return_value = []
        self.mock_main_time_sleep.side_effect = lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop")) # More aggressive interrupt

        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        self.mock_get_historical_candles.assert_not_called()
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], int(last_processed_dt.timestamp() * 1000))
        self.mock_main_time_sleep.assert_called_once() # Should be called once for the main loop sleep


    def test_poll_initializes_last_timestamp_if_missing(self):
        current_time_utc = datetime(2023, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = current_time_utc
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        
        self.last_processed_timestamps.clear() 
        self.mock_get_historical_candles.return_value = []
        self.mock_main_time_sleep.side_effect = lambda t: (_ for _ in ()).throw(KeyboardInterrupt("Stop loop")) # More aggressive

        with self.assertRaises(KeyboardInterrupt):
             candle_ingestor_main.run_polling_loop(
                self.mock_influx_manager, self.tiingo_tickers, FLAGS.tiingo_api_key,
                FLAGS.candle_granularity_minutes, 0, FLAGS.polling_initial_catchup_days,
                self.last_processed_timestamps
            )
        
        self.assertIn(self.test_ticker, self.last_processed_timestamps)
        expected_init_ts_ms = int((current_time_utc - timedelta(days=FLAGS.polling_initial_catchup_days)).timestamp() * 1000)
        self.assertEqual(self.last_processed_timestamps[self.test_ticker], expected_init_ts_ms)
        
        self.mock_get_historical_candles.assert_called_once()
        self.mock_influx_manager.write_candles_batch.assert_not_called()
        self.mock_main_time_sleep.assert_called_once()


if __name__ == "__main__":
    absltest.main()
