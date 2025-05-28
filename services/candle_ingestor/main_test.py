import sys
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.candle_ingestor import main as candle_ingestor_main
from services.candle_ingestor import influx_client as influx_client_module
from shared.cryptoclient import redis_crypto_client  # For mocking Redis client
from shared.persistence import influxdb_last_processed_tracker  # For mocking state tracker

FLAGS = flags.FLAGS


class BaseIngestorTest(absltest.TestCase):
    def setUp(self):
        super().setUp()

        self.mock_influx_manager = mock.MagicMock(
            spec=influx_client_module.InfluxDBManager
        )
        self.mock_influx_manager.get_client.return_value = self.mock_influx_manager
        self.mock_influx_manager.write_candles_batch.return_value = 1

        self.patch_influx_db_manager = mock.patch(
            "services.candle_ingestor.main.InfluxDBManager",
            return_value=self.mock_influx_manager,
        )
        self.mock_influx_db_manager_class = self.patch_influx_db_manager.start()
        self.addCleanup(self.patch_influx_db_manager.stop)

        # Mock InfluxDBLastProcessedTracker
        self.mock_state_tracker = mock.MagicMock(
            spec=influxdb_last_processed_tracker.InfluxDBLastProcessedTracker
        )
        self.mock_state_tracker.client = mock.MagicMock()  # Ensure client is not None
        self.mock_state_tracker.get_last_processed_timestamp.return_value = None
        self.mock_state_tracker.update_last_processed_timestamp.return_value = None

        self.patch_state_tracker = mock.patch(
            "services.candle_ingestor.main.InfluxDBLastProcessedTracker",
            return_value=self.mock_state_tracker,
        )
        self.mock_state_tracker_class = self.patch_state_tracker.start()
        self.addCleanup(self.patch_state_tracker.stop)

        # Mock RedisCryptoClient
        self.patch_redis_crypto_client = mock.patch(
            "services.candle_ingestor.main.RedisCryptoClient"
        )
        self.mock_redis_crypto_client_constructor = (
            self.patch_redis_crypto_client.start()
        )
        self.mock_redis_client_instance = mock.MagicMock(
            spec=redis_crypto_client.RedisCryptoClient
        )
        self.mock_redis_client_instance.client = mock.MagicMock()
        self.mock_redis_crypto_client_constructor.return_value = (
            self.mock_redis_client_instance
        )
        self.mock_redis_client_instance.get_client = mock.MagicMock(return_value=True)

        self.addCleanup(self.patch_redis_crypto_client.stop)

        self.patch_get_historical_candles = mock.patch(
            "services.candle_ingestor.main.get_historical_candles_tiingo"
        )
        self.mock_get_historical_candles = self.patch_get_historical_candles.start()
        self.addCleanup(self.patch_get_historical_candles.stop)

        self.patch_time_sleep = mock.patch("services.candle_ingestor.main.time.sleep")
        self.mock_time_sleep = self.patch_time_sleep.start()
        self.addCleanup(self.patch_time_sleep.stop)

        self.patch_main_datetime_now = mock.patch(
            "services.candle_ingestor.main.datetime"
        )
        self.mock_main_datetime_module = self.patch_main_datetime_now.start()
        self.addCleanup(self.patch_main_datetime_now.stop)

        self.patch_helpers_datetime_now = mock.patch(
            "services.candle_ingestor.ingestion_helpers.datetime"
        )
        self.mock_helpers_datetime_module = self.patch_helpers_datetime_now.start()
        self.addCleanup(self.patch_helpers_datetime_now.stop)

        self.mock_main_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_main_datetime_module.strptime = datetime.strptime
        self.mock_main_datetime_module.side_effect = lambda *args, **kwargs: datetime(
            *args, **kwargs
        )
        self.mock_main_datetime_module.timezone = timezone

        self.mock_helpers_datetime_module.fromtimestamp = datetime.fromtimestamp
        self.mock_helpers_datetime_module.strptime = datetime.strptime
        self.mock_helpers_datetime_module.side_effect = (
            lambda *args, **kwargs: datetime(*args, **kwargs)
        )
        self.mock_helpers_datetime_module.timezone = timezone

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.tiingo_api_key = "dummy_tiingo_for_test"
        FLAGS.influxdb_token = "dummy_influx_token_for_test"
        FLAGS.influxdb_org = "dummy_influx_org_for_test"
        FLAGS.redis_host = "dummy_redis_host_for_test"  # Added
        FLAGS.redis_key_crypto_symbols = "test_crypto_symbols"  # Added
        FLAGS.candle_granularity_minutes = 1
        FLAGS.catch_up_initial_days = 1
        FLAGS.tiingo_api_call_delay_seconds = 0
        FLAGS.backfill_start_date = "1_day_ago"

        self.test_ticker = "btcusd"
        self.tiingo_tickers = [
            self.test_ticker,
            "ethusd",
        ]
        # Mock Redis to return these tickers
        self.mock_redis_client_instance.get_top_crypto_pairs_from_redis.return_value = (
            self.tiingo_tickers
        )

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
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "1_day_ago"
        self.mock_state_tracker.get_last_processed_timestamp.return_value = None

        expected_candle_ts_for_fetch_start = (
            datetime(2023, 1, 9, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        dummy_candle = self._create_dummy_candle(expected_candle_ts_for_fetch_start)
        self.mock_get_historical_candles.return_value = [dummy_candle]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            state_tracker=self.mock_state_tracker,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
            dry_run_processing_limit=None,
        )
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-09", "2023-01-09", mock.ANY
        )
        self.mock_state_tracker.update_last_processed_timestamp.assert_called_with(
            candle_ingestor_main.SERVICE_IDENTIFIER, 
            f"{self.test_ticker}-backfill", 
            dummy_candle["timestamp_ms"]
        )
        self.assertEqual(
            self.last_processed_timestamps_shared_state[self.test_ticker],
            dummy_candle["timestamp_ms"],
        )

    def test_backfill_resumes_from_db_state(self):
        self._set_current_time("2023-01-10T12:00:00")
        FLAGS.backfill_start_date = "5_days_ago"
        db_resume_timestamp_ms = int(
            datetime(2023, 1, 7, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.mock_state_tracker.get_last_processed_timestamp.return_value = (
            db_resume_timestamp_ms
        )

        expected_candle_ts_for_fetch = (
            datetime(2023, 1, 7, 0, 1, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        dummy_candle_resumed = self._create_dummy_candle(expected_candle_ts_for_fetch)
        self.mock_get_historical_candles.return_value = [dummy_candle_resumed]

        candle_ingestor_main.run_backfill(
            influx_manager=self.mock_influx_manager,
            state_tracker=self.mock_state_tracker,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            backfill_start_date_str=FLAGS.backfill_start_date,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
            dry_run_processing_limit=None,
        )
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-07", "2023-01-09", mock.ANY
        )
        self.mock_state_tracker.update_last_processed_timestamp.assert_called_with(
            candle_ingestor_main.SERVICE_IDENTIFIER,
            f"{self.test_ticker}-backfill", 
            dummy_candle_resumed["timestamp_ms"]
        )


class RunCatchUpTest(BaseIngestorTest):
    def test_catch_up_from_backfill_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        backfill_state_ms = int(
            datetime(2023, 1, 10, 11, 58, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        self.last_processed_timestamps_shared_state[self.test_ticker] = (
            backfill_state_ms
        )
        self.mock_state_tracker.get_last_processed_timestamp.return_value = None

        expected_catch_up_candle_ts = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(expected_catch_up_candle_ts)
        self.mock_get_historical_candles.return_value = [polled_candle]

        candle_ingestor_main.run_catch_up(
            influx_manager=self.mock_influx_manager,
            state_tracker=self.mock_state_tracker,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
            dry_run_processing_limit=None,
        )

        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T11:59:00",
            "2023-01-10T12:05:00",
            mock.ANY,
        )
        self.mock_state_tracker.update_last_processed_timestamp.assert_called_with(
            candle_ingestor_main.SERVICE_IDENTIFIER,
            f"{self.test_ticker}-catch_up", 
            polled_candle["timestamp_ms"]
        )
        self.assertEqual(
            self.last_processed_timestamps_shared_state[self.test_ticker],
            polled_candle["timestamp_ms"],
        )

    def test_catch_up_from_db_catch_up_state(self):
        self._set_current_time("2023-01-10T12:05:00")
        catch_up_db_state_ms = int(
            datetime(2023, 1, 10, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        # Mock the state tracker to return catch_up state on first call, None on second
        self.mock_state_tracker.get_last_processed_timestamp.side_effect = (
            lambda service, key: (catch_up_db_state_ms if "catch_up" in key else None)
        )

        expected_catch_up_candle_ts = int(
            datetime(2023, 1, 10, 12, 1, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        polled_candle = self._create_dummy_candle(expected_catch_up_candle_ts)
        self.mock_get_historical_candles.return_value = [polled_candle]

        candle_ingestor_main.run_catch_up(
            influx_manager=self.mock_influx_manager,
            state_tracker=self.mock_state_tracker,
            tiingo_tickers=[self.test_ticker],
            tiingo_api_key=FLAGS.tiingo_api_key,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            api_call_delay_seconds=FLAGS.tiingo_api_call_delay_seconds,
            initial_catch_up_days=FLAGS.catch_up_initial_days,
            last_processed_timestamps=self.last_processed_timestamps_shared_state,
            run_mode="wet",
            dry_run_processing_limit=None,
        )
        self.mock_state_tracker.get_last_processed_timestamp.assert_any_call(
            candle_ingestor_main.SERVICE_IDENTIFIER,
            f"{self.test_ticker}-catch_up"
        )
        self.mock_get_historical_candles.assert_called_with(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-10T12:01:00",
            "2023-01-10T12:05:00",
            mock.ANY,
        )


class MainFunctionTest(BaseIngestorTest):
    @flagsaver.flagsaver(backfill_start_date="skip", run_mode="dry")
    def test_main_dry_run_skip_backfill_runs_catch_up(self):
        self._set_current_time("2023-01-02T00:00:00")
        with mock.patch.object(sys, "exit") as mock_exit:
            candle_ingestor_main.main(None)
            mock_exit.assert_called_once_with(0)

        # In dry mode, get_historical_candles_tiingo should not be called
        self.assertEqual(self.mock_get_historical_candles.call_count, 0)

    @flagsaver.flagsaver(run_mode="wet")
    def test_main_wet_run_executes_backfill_and_catch_up(self):
        self._set_current_time("2023-01-03T00:00:00")
        FLAGS.backfill_start_date = "2_days_ago"
        FLAGS.catch_up_initial_days = 1

        # Mock Redis
        self.mock_redis_client_instance.get_top_crypto_pairs_from_redis.return_value = [
            self.test_ticker
        ]

        self.mock_state_tracker.get_last_processed_timestamp.return_value = None

        backfill_candle_ts = int(
            datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        backfill_candles_response = [
            self._create_dummy_candle(backfill_candle_ts, pair=self.test_ticker)
        ]

        catch_up_candle_ts = int(
            datetime(2023, 1, 2, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
        )
        catch_up_candles_response = [
            self._create_dummy_candle(
                catch_up_candle_ts, pair=self.test_ticker, close_price=110
            )
        ]

        self.mock_get_historical_candles.side_effect = [
            backfill_candles_response,
            catch_up_candles_response,
        ]

        with mock.patch.object(sys, "exit") as mock_exit:
            candle_ingestor_main.main(None)
            mock_exit.assert_called_once_with(0)

        self.assertEqual(self.mock_get_historical_candles.call_count, 2)
        self.mock_get_historical_candles.assert_any_call(
            FLAGS.tiingo_api_key, self.test_ticker, "2023-01-01", "2023-01-02", mock.ANY
        )
        self.mock_get_historical_candles.assert_any_call(
            FLAGS.tiingo_api_key,
            self.test_ticker,
            "2023-01-01T10:01:00",
            "2023-01-03T00:00:00",
            mock.ANY,
        )

        self.mock_influx_manager.write_candles_batch.assert_any_call(
            backfill_candles_response
        )
        self.mock_influx_manager.write_candles_batch.assert_any_call(
            catch_up_candles_response
        )
        self.mock_state_tracker.update_last_processed_timestamp.assert_any_call(
            candle_ingestor_main.SERVICE_IDENTIFIER,
            f"{self.test_ticker}-backfill",
            backfill_candle_ts,
        )
        self.mock_state_tracker.update_last_processed_timestamp.assert_any_call(
            candle_ingestor_main.SERVICE_IDENTIFIER,
            f"{self.test_ticker}-catch_up",
            catch_up_candle_ts,
        )
        self.mock_redis_client_instance.close.assert_called_once()  # Verify Redis client is closed
        self.mock_state_tracker.close.assert_called_once()  # Verify state tracker is closed


if __name__ == "__main__":
    absltest.main()
