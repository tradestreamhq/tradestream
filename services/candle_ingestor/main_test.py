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
        candle_ingestor_main.shutdown_requested = False
        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None
        self.mock_influx_manager.update_last_processed_timestamp.return_value = None
        self.mock_influx_manager.write_candles_batch.return_value = 1

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

        self.patch_helpers_datetime = mock.patch(
            "services.candle_ingestor.ingestion_helpers.datetime"
        )
        self.mock_helpers_datetime_module = self.patch_helpers_datetime.start()
        self.addCleanup(self.patch_helpers_datetime.stop)

        self.patch_main_timedelta = mock.patch(
            "services.candle_ingestor.main.timedelta", timedelta
        )
        self.patch_main_timedelta.start()
        self.addCleanup(self.patch_main_timedelta.stop)

        self.patch_helpers_timedelta = mock.patch(
            "services.candle_ingestor.ingestion_helpers.timedelta", timedelta
        )
        self.patch_helpers_timedelta.start()
        self.addCleanup(self.patch_helpers_timedelta.stop)

        self.mock_main_datetime_module.now = mock.MagicMock()
        self.mock_helpers_datetime_module.now = self.mock_main_datetime_module.now

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

        self.mock_main_datetime_module.timezone = timezone
        self.mock_helpers_datetime_module.timezone = timezone

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc_for_test"
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.influxdb_token = "dummy_influx_token_for_test"
        FLAGS.influxdb_org = "dummy_influx_org_for_test"
        FLAGS.candle_granularity_minutes = 1
        FLAGS.polling_initial_catchup_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0
        FLAGS.backfill_start_date = "1_day_ago"

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [self.test_ticker]
        self.last_processed_candle_timestamps_for_backfill = {}
        self.last_processed_timestamps_for_polling = {}

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        candle_ingestor_main.shutdown_requested = False
        super().tearDown()

    def _set_current_time(self, dt_str):
        mock_dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        self.mock_main_datetime_module.now.return_value = mock_dt
        self.mock_helpers_datetime_module.now.return_value = mock_dt

        def mock_datetime_constructor(*args, **kwargs):
            return datetime(*args, **kwargs)

        self.mock_main_datetime_module.side_effect = mock_datetime_constructor
        self.mock_helpers_datetime_module.side_effect = mock_datetime_constructor

        self.mock_main_datetime_module.timezone = timezone
        self.mock_helpers_datetime_module.timezone = timezone

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
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        dummy_candle = self._create_dummy_candle(
            datetime(2023, 1, 9, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_get_historical_candles.return_value = [dummy_candle]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps={},
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle["timestamp_ms"]
        )

    def test_backfill_resumes_from_db_state(self):
        """Test backfill resumes from existing DB state when available."""
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "5_days_ago"
        db_resume_timestamp_ms = int(
            datetime(2023, 1, 7, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )

        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            db_resume_timestamp_ms
        )

        expected_fetch_start_dt = datetime(2023, 1, 7, 0, 1, 0, tzinfo=timezone.utc)
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
            last_backfilled_timestamps={},
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-07", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle_resumed["timestamp_ms"]
        )

    def test_backfill_db_state_is_after_flag_start_date(self):
        """Test backfill uses flag date when it's later than DB state."""
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"
        db_older_timestamp_ms = int(
            datetime(2023, 1, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )

        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            db_older_timestamp_ms
        )

        expected_fetch_start_dt = datetime(2023, 1, 9, 12, 0, 0, tzinfo=timezone.utc)
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
            last_backfilled_timestamps={},
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", mock.ANY, mock.ANY
        )
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            self.test_ticker, "backfill", dummy_candle["timestamp_ms"]
        )

    def test_backfill_dry_run_mode(self):
        """Test backfill in dry run mode with limited iterations."""
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"

        initial_backfill_timestamps = {}

        candle_ingestor_main.run_backfill(
            influx_manager=None,
            tiingo_tickers=["btcusd-dry", "ethusd-dry"],
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps=initial_backfill_timestamps,
            run_mode="dry",
        )

        self.mock_get_historical_candles.assert_not_called()
        self.assertIn("btcusd-dry", initial_backfill_timestamps)
        self.assertTrue(candle_ingestor_main.shutdown_requested)

    def test_backfill_with_shutdown_requested(self):
        """Test backfill behavior when shutdown is requested."""
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"

        candle_ingestor_main.shutdown_requested = True

        initial_backfill_timestamps = {}

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps=initial_backfill_timestamps,
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_not_called()
        self.mock_influx_manager.update_last_processed_timestamp.assert_not_called()

    def test_backfill_skip_already_completed_ticker(self):
        """Test backfill skips ticker that's already completed."""
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"

        already_completed_timestamp_ms = int(
            datetime(2023, 1, 11, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.return_value = (
            already_completed_timestamp_ms
        )

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_backfilled_timestamps={},
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_not_called()


class RunPollingLoopTest(BaseIngestorTest):
    def test_polling_initializes_from_polling_db_state(self):
        """Test polling loop uses existing polling state when available."""
        self._set_current_time("2023-01-10T12:05:00")
        polling_db_state_ms = int(
            datetime(2023, 1, 10, 11, 58, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (polling_db_state_ms if type == "polling" else None)
        )

        candle_12_00_ts = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(candle_12_00_ts)
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
            run_mode="wet",
        )

        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "polling"
        )
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
        """Test polling falls back to backfill state when no polling state exists."""
        self._set_current_time("2023-01-10T12:05:00")
        backfill_db_state_ms = int(
            datetime(2023, 1, 10, 11, 50, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (backfill_db_state_ms if type == "backfill" else None)
        )

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
            last_processed_timestamps=last_processed_timestamps_from_main,
            run_mode="wet",
        )

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
        """Test polling uses default catchup period when no DB state exists."""
        self._set_current_time("2023-01-10T12:05:00")
        FLAGS.polling_initial_catchup_days = 3
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        expected_initial_seed_ms = int(
            datetime(2023, 1, 7, 12, 5, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(expected_initial_seed_ms + 60000)
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
            run_mode="wet",
        )

        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "polling"
        )
        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "backfill"
        )
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

    def test_polling_dry_run_mode(self):
        """Test polling in dry run mode with limited cycles."""
        self._set_current_time("2023-01-10T12:05:00")

        last_processed_timestamps_arg = {}

        candle_ingestor_main.run_polling_loop(
            influx_manager=None,
            tiingo_tickers=["btcusd-dry"],
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
            run_mode="dry",
        )

        self.mock_get_historical_candles.assert_not_called()
        self.assertTrue(candle_ingestor_main.shutdown_requested)

    def test_polling_with_shutdown_requested_during_initialization(self):
        """Test polling behavior when shutdown is requested during initialization."""
        self._set_current_time("2023-01-10T12:05:00")
        candle_ingestor_main.shutdown_requested = True

        last_processed_timestamps_arg = {}

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_not_called()

    def test_polling_skips_already_processed_candle(self):
        """Test polling skips candles that are already processed."""
        self._set_current_time("2023-01-10T12:05:00")

        recent_timestamp_ms = int(
            datetime(2023, 1, 10, 12, 4, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        last_processed_timestamps_arg = {self.test_ticker: recent_timestamp_ms}

        self.mock_main_time_sleep.side_effect = KeyboardInterrupt

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=self.tiingo_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
            run_mode="wet",
        )

        self.mock_get_historical_candles.assert_not_called()

    def test_polling_handles_missing_timestamp_gracefully(self):
        """Test polling handles missing timestamp for a ticker gracefully."""
        self._set_current_time("2023-01-10T12:05:00")
        self.mock_influx_manager.get_last_processed_timestamp.return_value = None

        last_processed_timestamps_arg = {}

        polled_candle = self._create_dummy_candle(
            int(datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
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
            last_processed_timestamps=last_processed_timestamps_arg,
            run_mode="wet",
        )

        self.assertIn(self.test_ticker, last_processed_timestamps_arg)

    def test_polling_handles_exception_for_ticker(self):
        """Test polling continues processing other tickers when one ticker fails."""
        self._set_current_time("2023-01-10T12:05:00")

        multi_tickers = ["btcusd", "ethusd"]

        last_processed_timestamps_arg = {
            "btcusd": int(
                datetime(2023, 1, 10, 11, 50, 0, tzinfo=timezone.utc).timestamp() * 1000
            ),
            "ethusd": int(
                datetime(2023, 1, 10, 11, 50, 0, tzinfo=timezone.utc).timestamp() * 1000
            ),
        }

        def get_candles_side_effect(api_key, ticker, start, end, freq):
            if ticker == "btcusd":
                raise Exception("API error for btcusd")
            return [
                self._create_dummy_candle(
                    int(
                        datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp()
                        * 1000
                    ),
                    pair=ticker,
                )
            ]

        self.mock_get_historical_candles.side_effect = get_candles_side_effect
        self.mock_main_time_sleep.side_effect = KeyboardInterrupt

        candle_ingestor_main.run_polling_loop(
            influx_manager=self.mock_influx_manager,
            tiingo_tickers=multi_tickers,
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catchup_days=FLAGS.polling_initial_catchup_days,
            last_processed_timestamps=last_processed_timestamps_arg,
            run_mode="wet",
        )

        self.assertIn("btcusd", last_processed_timestamps_arg)
        self.assertIn("ethusd", last_processed_timestamps_arg)
        self.mock_influx_manager.update_last_processed_timestamp.assert_called_with(
            "ethusd", "polling", mock.ANY
        )


class MainFunctionTest(BaseIngestorTest):
    @flagsaver.flagsaver(backfill_start_date="skip")
    @mock.patch("services.candle_ingestor.main.run_polling_loop")
    @mock.patch("services.candle_ingestor.main.run_backfill")
    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_skip_backfill_initializes_polling_correctly(
        self, MockInfluxDBManager, mock_run_backfill, mock_run_polling_loop
    ):
        """Test main function skips backfill when configured and initializes polling."""
        MockInfluxDBManager.return_value = self.mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

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

        candle_ingestor_main.main(None)

        mock_run_backfill.assert_not_called()
        mock_run_polling_loop.assert_called_once()
        args, kwargs = mock_run_polling_loop.call_args
        passed_last_processed_timestamps = kwargs["last_processed_timestamps"]
        self.assertEqual(passed_last_processed_timestamps, {})

    @flagsaver.flagsaver(backfill_start_date="1_day_ago")
    @mock.patch("services.candle_ingestor.main.run_polling_loop")
    @mock.patch("services.candle_ingestor.main.run_backfill")
    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_with_backfill_populates_timestamps_for_backfill_call(
        self, MockInfluxDBManager, mock_run_backfill, mock_run_polling_loop
    ):
        """Test main function populates timestamps correctly for backfill."""
        MockInfluxDBManager.return_value = self.mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        db_backfill_state_ms = int(
            datetime(2023, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_influx_manager.get_last_processed_timestamp.side_effect = (
            lambda symbol, type: (db_backfill_state_ms if type == "backfill" else None)
        )

        candle_ingestor_main.main(None)

        self.mock_influx_manager.get_last_processed_timestamp.assert_any_call(
            self.test_ticker, "backfill"
        )

        mock_run_backfill.assert_called_once()
        args_backfill, kwargs_backfill = mock_run_backfill.call_args
        passed_timestamps_to_backfill = kwargs_backfill["last_backfilled_timestamps"]
        self.assertEqual(
            passed_timestamps_to_backfill.get(self.test_ticker), db_backfill_state_ms
        )

        mock_run_polling_loop.assert_called_once()

    @flagsaver.flagsaver(run_mode="dry")
    @mock.patch("services.candle_ingestor.main.run_polling_loop")
    @mock.patch("services.candle_ingestor.main.run_backfill")
    def test_main_dry_run_mode_skips_influxdb(
        self, mock_run_backfill, mock_run_polling_loop
    ):
        """Test main function in dry run mode skips InfluxDB initialization."""
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        candle_ingestor_main.main(None)

        mock_run_backfill.assert_called_once()
        args_backfill, kwargs_backfill = mock_run_backfill.call_args
        self.assertIsNone(kwargs_backfill["influx_manager"])
        self.assertEqual(kwargs_backfill["run_mode"], "dry")

        mock_run_polling_loop.assert_called_once()
        args_polling, kwargs_polling = mock_run_polling_loop.call_args
        self.assertIsNone(kwargs_polling["influx_manager"])
        self.assertEqual(kwargs_polling["run_mode"], "dry")

    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_exits_early_if_influxdb_connection_fails(self, MockInfluxDBManager):
        """Test main function exits early if InfluxDB connection fails."""
        mock_influx_manager = mock.MagicMock()
        mock_influx_manager.get_client.return_value = None
        MockInfluxDBManager.return_value = mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        result = candle_ingestor_main.main(None)

        self.assertEqual(result, 1)
        self.mock_get_top_n_crypto_symbols.assert_not_called()

    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_exits_early_if_no_symbols_fetched(self, MockInfluxDBManager):
        """Test main function exits early if no symbols are fetched."""
        MockInfluxDBManager.return_value = self.mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = []

        result = candle_ingestor_main.main(None)

        self.assertEqual(result, 1)

    @mock.patch("services.candle_ingestor.main.signal.signal")
    @mock.patch("services.candle_ingestor.main.InfluxDBManager")
    def test_main_sets_up_signal_handlers(self, MockInfluxDBManager, mock_signal):
        """Test main function sets up signal handlers."""
        MockInfluxDBManager.return_value = self.mock_influx_manager
        self.mock_get_top_n_crypto_symbols.return_value = self.tiingo_tickers

        candle_ingestor_main.main(None)

        self.assertEqual(mock_signal.call_count, 2)

    @flagsaver.flagsaver(run_mode="dry", backfill_start_date="skip")
    def test_main_dry_run_uses_dummy_symbols(self):
        """Test main function uses dummy symbols in dry run mode."""
        with self.assertRaises(SystemExit) as cm:
            candle_ingestor_main.main(None)
        self.assertEqual(cm.exception.code, 0)

        self.mock_get_top_n_crypto_symbols.assert_not_called()


class SignalHandlerTest(BaseIngestorTest):
    """Test signal handling functionality."""

    @mock.patch("services.candle_ingestor.main.signal.Signals")
    def test_shutdown_signal_handler_sets_flag_and_closes_influx(self, mock_signals):
        """Test shutdown signal handler sets flag and closes InfluxDB connection."""
        candle_ingestor_main.influx_manager_global = self.mock_influx_manager
        candle_ingestor_main.shutdown_requested = False
        mock_signals.return_value.name = "SIGTERM"

        candle_ingestor_main.handle_shutdown_signal(15, None)

        self.assertTrue(candle_ingestor_main.shutdown_requested)
        self.mock_influx_manager.close.assert_called_once()

    @mock.patch("services.candle_ingestor.main.signal.Signals")
    def test_shutdown_signal_handler_handles_influx_close_exception(self, mock_signals):
        """Test shutdown signal handler handles InfluxDB close exceptions gracefully."""
        candle_ingestor_main.influx_manager_global = self.mock_influx_manager
        candle_ingestor_main.shutdown_requested = False
        mock_signals.return_value.name = "SIGINT"
        self.mock_influx_manager.close.side_effect = Exception("Close failed")

        candle_ingestor_main.handle_shutdown_signal(2, None)

        self.assertTrue(candle_ingestor_main.shutdown_requested)
        self.mock_influx_manager.close.assert_called_once()

    @mock.patch("services.candle_ingestor.main.signal.Signals")
    def test_shutdown_signal_handler_with_no_influx_manager(self, mock_signals):
        """Test shutdown signal handler when no InfluxDB manager is set."""
        candle_ingestor_main.influx_manager_global = None
        candle_ingestor_main.shutdown_requested = False
        mock_signals.return_value.name = "SIGTERM"

        candle_ingestor_main.handle_shutdown_signal(15, None)

        self.assertTrue(candle_ingestor_main.shutdown_requested)


if __name__ == "__main__":
    absltest.main()
