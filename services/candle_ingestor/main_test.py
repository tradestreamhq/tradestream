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


class BaseIngestorTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        candle_ingestor_main.shutdown_requested = False  # Reset global flag
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )
        # Configure default return values for new state methods
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None
        self.mock_influx_manager.update_last_processed_timestamp.return_value = None
        self.mock_influx_manager.write_candles_batch.return_value = (
            1  # Simulate successful write
        )

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

        self.patch_main_time_sleep = mock.patch(
            "services.candle_ingestor.main.time.sleep"
        )
        self.mock_main_time_sleep = self.patch_main_time_sleep.start()
        self.addCleanup(self.patch_main_time_sleep.stop)

        self.patch_main_datetime = mock.patch("services.candle_ingestor.main.datetime")
        self.mock_main_datetime_module = self.patch_main_datetime.start()
        self.addCleanup(self.patch_main_datetime.stop)

        # Patch the datetime in ingestion_helpers too, to ensure consistent mocking
        self.patch_helpers_datetime = mock.patch(
            "services.candle_ingestor.ingestion_helpers.datetime"
        )
        self.mock_helpers_datetime_module = self.patch_helpers_datetime.start()
        self.addCleanup(self.patch_helpers_datetime.stop)

        # Configure datetime mocks
        self.mock_main_datetime_module.now = mock.MagicMock()
        self.mock_helpers_datetime_module.now = self.mock_main_datetime_module.now

        # Configure non-mocked parts
        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime_module.strptime = datetime.strptime
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(
            *args, **kwargs
        )

        self.mock_helpers_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_helpers_datetime_module.strptime = datetime.strptime
        self.mock_helpers_datetime_module.side_effect = (
            lambda *args, **kwargs: datetime(*args, **kwargs)
        )

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc_for_test"
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.influxdb_token = "dummy_influx_token_for_test"
        FLAGS.influxdb_org = "dummy_influx_org_for_test"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0
        FLAGS.backfill_start_date = "1_day_ago"  # Default for some tests

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        self.last_processed_candle_timestamps_for_backfill = (
            {}
        )  # Used to pass to run_backfill
        self.last_processed_timestamps_for_polling = {}  # Used to pass to run_polling

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        super().tearDown()

    def _set_current_time(self, dt_str):
        mock_dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
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
        self._set_current_time("2023-01-10T12:00:00")  # "now" for parsing "1_day_ago"
        FLAGS.backfill_start_date = "1_day_ago"  # Effective start: 2023-01-09T12:00:00
        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            None  # No DB state
        )

        dummy_candle = self._create_dummy_candle(
            datetime(2023, 1, 9, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_get_historical_candles.return_value = [dummy_candle]

        initial_backfill_timestamps = {}  # Empty, main will populate based on DB calls

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps=initial_backfill_timestamps,  # Passed from main
        )
        # run_backfill itself now queries DB if last_backfilled_timestamps is empty or misses a ticker
        # The initial call from main() pre-populates last_backfilled_timestamps
        # Here, we are testing the case where main's pre-population found nothing for this ticker

        # Assertions
        # Check if Tiingo was called with the date derived from FLAGS.backfill_start_date
        # expected_start_date_str for Tiingo API (YYYY-MM-DD)
        # "now" is 2023-01-10, "1_day_ago" is 2023-01-09 for chunk start
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle["timestamp_ms"]
        )

    def test_backfill_resumes_from_db_state(self):
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "5_days_ago"  # Flag start: 2023-01-05T12:00:00
        db_resume_timestamp_ms = int(
            datetime(2023, 1, 7, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )

        # Simulate that main() pre-populated this from DB
        initial_backfill_timestamps = {self.test_ticker: db_resume_timestamp_ms}

        # Candles that would be fetched after resuming
        expected_fetch_start_dt = datetime(
            2023, 1, 7, 0, 1, 0, tzinfo=timezone.utc
        )  # db_resume_ts + 1 min
        dummy_candle_resumed = self._create_dummy_candle(
            int(expected_fetch_start_dt.timestamp() * 1000)
        )
        self.mock_get_historical_candles.return_value = [dummy_candle_resumed]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps=initial_backfill_timestamps,  # Pass pre-populated dict
        )

        # Assert that Tiingo is called starting from the day of (db_resume_timestamp + granularity)
        # db_resume is 2023-01-07 00:00. next candle is 00:01. Tiingo historical takes YYYY-MM-DD.
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-07", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle_resumed["timestamp_ms"]
        )

    def test_backfill_db_state_is_after_flag_start_date(self):
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"  # Flag start: 2023-01-09T12:00:00
        # DB state is *older* than flag start, so flag start should take precedence for earliest point
        db_older_timestamp_ms = int(
            datetime(2023, 1, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )

        initial_backfill_timestamps = {self.test_ticker: db_older_timestamp_ms}

        expected_fetch_start_dt = datetime(
            2023, 1, 9, 12, 0, 0, tzinfo=timezone.utc
        )  # From flag
        dummy_candle = self._create_dummy_candle(
            int(expected_fetch_start_dt.timestamp() * 1000)
        )
        self.mock_get_historical_candles.return_value = [dummy_candle]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps=initial_backfill_timestamps,
        )
        # Expected fetch start day should be 2023-01-09 (from flag as it's later than DB state + delta)
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle["timestamp_ms"]
        )


class RunPollingLoopTest(BaseIngestorTest):
    def test_polling_initializes_from_polling_db_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        polling_db_state_ms = int(
            datetime(2023, 1, 10, 11, 58, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (polling_db_state_ms if type == "polling" else None)
        )

        # Candle that would be fetched after resuming
        expected_fetch_start_dt = datetime(
            2023, 1, 10, 11, 59, 0, tzinfo=timezone.utc
        )  # polling_db_state_ms + 1min
        # Polling loop looks for candles up to current time - granularity
        # Current time 12:05, granularity 1 min -> target_latest_closed_candle_start = 12:04
        # query_start = 11:59, query_end = 12:04
        # So, candles from 11:59, 12:00, 12:01, 12:02, 12:03, 12:04 are candidates if Tiingo returns them.
        # Let's say Tiingo returns one for 12:00
        candle_12_00_ts = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(candle_12_00_ts)
        self.mock_get_historical_candles.return_value = [polled_candle]

        self.mock_main_time_sleep.side_effect = KeyboardInterrupt  # Stop after one loop

        last_processed_timestamps_arg = (
            {}
        )  # main.py passes this, polling loop initializes it

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
        )

        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "polling"
        )
        # Verify Tiingo called with start date derived from polling_db_state_ms + 1 min
        # polling_db_state_ms = 2023-01-10T11:58:00Z
        # query_start_dt_utc = 2023-01-10T11:59:00Z
        # query_end_dt_utc (effective_query_end_dt_utc) will be current_cycle_time_utc = 2023-01-10T12:05:00Z
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T11:59:00",
            "2023-01-10T12:05:00",
            mock.ANY,
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "polling", polled_candle["timestamp_ms"]
        )
        self.assertEqual(
            last_processed_timestamps_arg[self.test_ticker],
            polled_candle["timestamp_ms"],
        )

    def test_polling_initializes_from_backfill_db_state_if_no_polling_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        backfill_db_state_ms = int(
            datetime(2023, 1, 10, 11, 50, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        # Simulate polling returns None, backfill returns a value
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (backfill_db_state_ms if type == "backfill" else None)
        )

        # This dictionary will be populated by main() with the backfill state before polling loop is called
        last_processed_timestamps_from_main = {self.test_ticker: backfill_db_state_ms}

        polled_candle = self._create_dummy_candle(
            int(
                datetime(2023, 1, 10, 11, 51, 0, tzinfo=timezone.utc).timestamp() * 1000
            )
        )
        self.mock_get_historical_candles.return_value = [polled_candle]
        self.mock_main_time_sleep.side_effect = KeyboardInterrupt

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_from_main,  # Pass dict that main would have populated
        )

        # If "polling" was None, it would use the value from last_processed_timestamps_from_main (backfill state)
        # backfill_db_state_ms = 2023-01-10T11:50:00Z
        # query_start_dt_utc = 2023-01-10T11:51:00Z
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T11:51:00",
            "2023-01-10T12:05:00",
            mock.ANY,
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "polling", polled_candle["timestamp_ms"]
        )

    def test_polling_initializes_from_default_catchup_if_no_db_state(self):
        self._set_current_time("2023-01-10T12:05:00")  # "now"
        FLAGS.polling_initial_catchup_days = 3  # Catchup from 2023-01-07T12:05:00
        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            None  # No DB state at all
        )

        # Expected start: 2023-01-07T12:05:00 aligned to 1-min granularity -> 2023-01-07T12:05:00
        # Polling query_start will be this + 1 min -> 2023-01-07T12:06:00
        expected_initial_seed_ms = int(
            datetime(2023, 1, 7, 12, 5, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(
            expected_initial_seed_ms + 60000
        )  # Candle for 12:06
        self.mock_get_historical_candles.return_value = [polled_candle]
        self.mock_main_time_sleep.side_effect = KeyboardInterrupt

        last_processed_timestamps_arg = {}

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
        )

        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "polling"
        )
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "backfill"
        )
        # Query start should be default_catchup_start_ms + granularity
        self.assertEqual(
            last_processed_timestamps_arg[self.test_ticker],
            polled_candle["timestamp_ms"],
        )
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-07T12:06:00",
            "2023-01-10T12:05:00",
            mock.ANY,
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "polling", polled_candle["timestamp_ms"]
        )


class MainFunctionTest(BaseIngestorTest):  # Inherit for shared mocks
    @flagsaver.flagsaver(
        backfill_start_date="skip"
    )  # Ensure backfill is skipped for this test
    @mock.patch("services.candle_ingestor.main.run_polling_loop")
    @mock.patch("services.candle_ingestor.main.run_backfill")  # Also mock backfill
    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_skip_backfill_initializes_polling_correctly(
        self, MockInfluxDBManager, mock_run_backfill, mock_run_polling_loop
    ):
        # Arrange
        MockInfluxDBManager.return_value = self.mock_influx_manager  # Use our instance
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        # Simulate DB states for polling initialization
        # No polling state, but a backfill state exists
        backfill_state_for_poll_init_ms = int(
            datetime(2023, 1, 9, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )

        def get_ts_side_effect(symbol, type):
            if type == "polling":
                return None
            if type == "backfill":
                return backfill_state_for_poll_init_ms
            return None

        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            get_ts_side_effect
        )

        # Act
        candle_ingestor_main.main(None)

        # Assert
        mock_run_backfill.assert_not_called()  # Backfill was skipped

        # Check arguments passed to run_polling_loop
        mock_run_polling_loop.assert_called_once()
        args, kwargs = mock_run_polling_loop.call_args
        passed_last_processed_timestamps = kwargs["last_processed_timestamps"]

        # Since backfill was skipped, the passed dict to polling should be empty initially.
        # The polling loop itself will query InfluxDB and find the backfill state.
        self.assertEqual(passed_last_processed_timestamps, {})

    @flagsaver.flagsaver(backfill_start_date="1_day_ago")
    @mock.patch("services.candle_ingestor.main.run_polling_loop")
    @mock.patch("services.candle_ingestor.main.run_backfill")
    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_with_backfill_populates_timestamps_for_backfill_call(
        self, MockInfluxDBManager, mock_run_backfill, mock_run_polling_loop
    ):
        # Arrange
        MockInfluxDBManager.return_value = self.mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        db_backfill_state_ms = int(
            datetime(2023, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (db_backfill_state_ms if type == "backfill" else None)
        )

        # Act
        candle_ingestor_main.main(None)

        # Assert
        # Check that get_last_processed_timestamp was called by main() to pre-populate for backfill
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "backfill"
        )

        mock_run_backfill.assert_called_once()
        args_backfill, kwargs_backfill = mock_run_backfill.call_args
        passed_timestamps_to_backfill = kwargs_backfill["last_backfilled_timestamps"]
        self.assertEqual(
            passed_timestamps_to_backfill.get(self.test_ticker), db_backfill_state_ms
        )

        # Polling loop should also be called, potentially with the dict updated by backfill
        mock_run_polling_loop.assert_called_once()
        args_polling, kwargs_polling = mock_run_polling_loop.call_args
        passed_timestamps_to_polling = kwargs_polling["last_processed_timestamps"]
        # This assertion depends on whether run_backfill modifies the dict in place.
        # If run_backfill modifies it, it should contain the latest from backfill.
        # If not, it will still be the initial DB state for backfill.
        # Given current run_backfill updates it in place (if new data fetched):
        # self.assertEqual(passed_timestamps_to_polling.get(self.test_ticker), ...)


if __name__ == "__main__":
    absltest.main()
