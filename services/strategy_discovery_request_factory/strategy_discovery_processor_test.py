"""Unit tests for strategy_discovery_processor module."""

import unittest
from unittest.mock import Mock, patch
import collections
from datetime import datetime, timezone

from protos.marketdata_pb2 import Candle
from protos.discovery_pb2 import StrategyDiscoveryRequest
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker

from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)


class StrategyDiscoveryProcessorTest(unittest.TestCase):
    """Test candle processing functionality."""

    def setUp(self):
        """Set up test environment."""
        self.fibonacci_windows = [5, 8, 13]  # Small windows for testing
        self.deque_maxlen = 50
        self.default_top_n = 3
        self.default_max_generations = 10
        self.default_population_size = 20
        self.candle_granularity_minutes = 1

    def _create_test_candle(
        self,
        currency_pair: str = "BTC/USD",
        timestamp_ms: int = None,
        open_price: float = 50000.0,
        high_price: float = 51000.0,
        low_price: float = 49000.0,
        close_price: float = 50500.0,
        volume: float = 1000.0,
    ) -> Candle:
        """Create a test candle."""
        if timestamp_ms is None:
            timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        ts_seconds = timestamp_ms // 1000
        ts_nanos = (timestamp_ms % 1000) * 1_000_000

        return Candle(
            timestamp=Timestamp(seconds=ts_seconds, nanos=ts_nanos),
            currency_pair=currency_pair,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )

    def _create_test_candles(
        self,
        count: int,
        currency_pair: str = "BTC/USD",
        start_timestamp_ms: int = None,
    ) -> list:
        """Create multiple test candles with sequential timestamps."""
        if start_timestamp_ms is None:
            start_timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        candles = []
        for i in range(count):
            timestamp_ms = start_timestamp_ms + (i * 60000)  # 1 minute intervals
            candle = self._create_test_candle(
                currency_pair=currency_pair,
                timestamp_ms=timestamp_ms,
                open_price=50000.0 + i,
                close_price=50050.0 + i,
            )
            candles.append(candle)
        return candles

    def test_initialization_without_tracker(self):
        """Test initialization without InfluxDB tracker."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=self.candle_granularity_minutes,
        )

        self.assertEqual(processor.fibonacci_windows_minutes, [5, 8, 13])
        self.assertEqual(processor.deque_maxlen, self.deque_maxlen)
        self.assertIsNone(processor.tracker)
        self.assertEqual(processor.service_identifier, "strategy_discovery_processor")
        self.assertEqual(len(processor.pair_deques), 0)
        self.assertEqual(len(processor.last_processed_timestamps), 0)

    def test_initialization_with_tracker(self):
        """Test initialization with InfluxDB tracker."""
        mock_tracker = Mock(spec=InfluxDBLastProcessedTracker)
        
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=self.candle_granularity_minutes,
            tracker=mock_tracker,
            service_identifier="test_service",
        )

        self.assertEqual(processor.tracker, mock_tracker)
        self.assertEqual(processor.service_identifier, "test_service")

    def test_initialize_pair_without_tracker(self):
        """Test initializing a currency pair without tracker."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        processor.initialize_pair("BTC/USD")

        self.assertIn("BTC/USD", processor.pair_deques)
        self.assertIsInstance(processor.pair_deques["BTC/USD"], collections.deque)
        self.assertEqual(processor.pair_deques["BTC/USD"].maxlen, self.deque_maxlen)
        self.assertEqual(len(processor.pair_deques["BTC/USD"]), 0)

    def test_initialize_pair_with_tracker(self):
        """Test initializing a currency pair with tracker."""
        mock_tracker = Mock(spec=InfluxDBLastProcessedTracker)
        mock_tracker.get_last_processed_timestamp.return_value = 1640995200000

        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
            tracker=mock_tracker,
            service_identifier="test_service",
        )

        processor.initialize_pair("BTC/USD")

        mock_tracker.get_last_processed_timestamp.assert_called_once_with(
            "test_service", "BTC/USD"
        )
        self.assertEqual(processor.last_processed_timestamps["BTC/USD"], 1640995200000)

    def test_initialize_pairs(self):
        """Test initializing multiple currency pairs."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        processor.initialize_pairs(["BTC/USD", "ETH/USD", "ADA/USD"])

        for pair in ["BTC/USD", "ETH/USD", "ADA/USD"]:
            self.assertIn(pair, processor.pair_deques)
            self.assertEqual(len(processor.pair_deques[pair]), 0)

    def test_add_candle_missing_currency_pair(self):
        """Test adding candle without currency pair."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        candle = self._create_test_candle(currency_pair="")
        requests = processor.add_candle(candle)

        self.assertEqual(len(requests), 0)
        self.assertEqual(len(processor.pair_deques), 0)

    def test_add_candle_auto_initialize_pair(self):
        """Test that adding candle auto-initializes pair."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        candle = self._create_test_candle("BTC/USD", timestamp_ms=1640995200000)
        requests = processor.add_candle(candle)

        # Pair should be auto-initialized
        self.assertIn("BTC/USD", processor.pair_deques)
        self.assertEqual(len(processor.pair_deques["BTC/USD"]), 1)
        self.assertEqual(processor.last_processed_timestamps["BTC/USD"], 1640995200000)

    def test_add_candle_old_timestamp_skipped(self):
        """Test that old candles are skipped."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        # Add first candle
        candle1 = self._create_test_candle("BTC/USD", timestamp_ms=1640995200000)
        processor.add_candle(candle1)

        # Try to add older candle
        candle2 = self._create_test_candle("BTC/USD", timestamp_ms=1640995100000)  # Older
        requests = processor.add_candle(candle2)

        # Should be skipped
        self.assertEqual(len(requests), 0)
        self.assertEqual(len(processor.pair_deques["BTC/USD"]), 1)
        self.assertEqual(processor.last_processed_timestamps["BTC/USD"], 1640995200000)

    def test_add_candle_updates_tracker(self):
        """Test that tracker is updated when candle is added."""
        mock_tracker = Mock(spec=InfluxDBLastProcessedTracker)
        mock_tracker.get_last_processed_timestamp.return_value = None

        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
            tracker=mock_tracker,
            service_identifier="test_service",
        )

        candle = self._create_test_candle("BTC/USD", timestamp_ms=1640995200000)
        processor.add_candle(candle)

        mock_tracker.update_last_processed_timestamp.assert_called_once_with(
            "test_service", "BTC/USD", 1640995200000
        )

    def test_add_candle_insufficient_for_windows(self):
        """Test that insufficient candles don't generate requests."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        # Add only 3 candles (less than smallest window of 5)
        candles = self._create_test_candles(3, "BTC/USD")
        all_requests = []

        for candle in candles:
            requests = processor.add_candle(candle)
            all_requests.extend(requests)

        self.assertEqual(len(all_requests), 0)
        self.assertEqual(len(processor.pair_deques["BTC/USD"]), 3)

    def test_add_candle_generates_requests_for_window(self):
        """Test that sufficient candles generate requests."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        # Add 5 candles (enough for 5-minute window)
        candles = self._create_test_candles(5, "BTC/USD")
        all_requests = []

        for candle in candles:
            requests = processor.add_candle(candle)
            all_requests.extend(requests)

        # Should generate requests for 5-minute window when 5th candle is added
        # Number of strategy types (excluding UNSPECIFIED)
        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]

        # Only the last add_candle should generate requests
        final_requests = processor.add_candle(candles[-1])
        self.assertEqual(len(final_requests), len(expected_strategy_types))

        # Verify request structure
        for request in final_requests:
            self.assertEqual(request.symbol, "BTC/USD")
            self.assertNotEqual(request.strategy_type, StrategyType.UNSPECIFIED)
            self.assertGreater(request.end_time.seconds, request.start_time.seconds)
            self.assertEqual(request.top_n, processor.default_top_n)
            self.assertEqual(
                request.ga_config.max_generations, processor.default_max_generations
            )
            self.assertEqual(
                request.ga_config.population_size, processor.default_population_size
            )

    def test_add_candle_multiple_windows(self):
        """Test generating requests for multiple windows."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        # Add 13 candles (enough for all windows: 5, 8, 13)
        candles = self._create_test_candles(13, "BTC/USD")

        for candle in candles[:-1]:  # Add all but last
            processor.add_candle(candle)

        # Add final candle and check requests
        final_requests = processor.add_candle(candles[-1])

        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]

        # Should generate requests for all 3 windows * number of strategy types
        expected_request_count = len(self.fibonacci_windows) * len(expected_strategy_types)
        self.assertEqual(len(final_requests), expected_request_count)

        # Verify window durations are represented
        unique_durations = set()
        for request in final_requests:
            duration_minutes = (request.end_time.seconds - request.start_time.seconds) // 60
            unique_durations.add(duration_minutes)

        self.assertEqual(sorted(unique_durations), self.fibonacci_windows)

    def test_deque_maxlen_behavior(self):
        """Test that deque respects maxlen."""
        small_maxlen = 10
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=small_maxlen,
        )

        # Add more candles than maxlen
        candles = self._create_test_candles(15, "BTC/USD")
        for candle in candles:
            processor.add_candle(candle)

        # Deque should only contain last 10 candles
        self.assertEqual(len(processor.pair_deques["BTC/USD"]), small_maxlen)

    def test_get_deque_status(self):
        """Test getting deque status."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        processor.initialize_pairs(["BTC/USD", "ETH/USD"])

        # Add some candles
        processor.add_candle(self._create_test_candle("BTC/USD"))
        processor.add_candle(self._create_test_candle("BTC/USD", timestamp_ms=1640995260000))
        processor.add_candle(self._create_test_candle("ETH/USD"))

        status = processor.get_deque_status()
        self.assertEqual(status["BTC/USD"], 2)
        self.assertEqual(status["ETH/USD"], 1)

    def test_get_last_processed_timestamps(self):
        """Test getting last processed timestamps."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        processor.add_candle(self._create_test_candle("BTC/USD", timestamp_ms=1640995200000))
        processor.add_candle(self._create_test_candle("ETH/USD", timestamp_ms=1640995300000))

        timestamps = processor.get_last_processed_timestamps()
        self.assertEqual(timestamps["BTC/USD"], 1640995200000)
        self.assertEqual(timestamps["ETH/USD"], 1640995300000)

        # Should be a copy, not the original dict
        timestamps["BTC/USD"] = 999
        self.assertEqual(processor.last_processed_timestamps["BTC/USD"], 1640995200000)

    def test_close(self):
        """Test processor cleanup."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        processor.initialize_pairs(["BTC/USD", "ETH/USD"])
        processor.add_candle(self._create_test_candle("BTC/USD"))

        processor.close()

        self.assertEqual(len(processor.pair_deques), 0)
        self.assertEqual(len(processor.last_processed_timestamps), 0)

    @patch("services.strategy_discovery_request_factory.strategy_discovery_processor.logging")
    def test_logging_behavior(self, mock_logging):
        """Test appropriate logging occurs."""
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
        )

        # Test initialization logging
        mock_logging.info.assert_called()

        # Test candle processing logging
        processor.add_candle(self._create_test_candle("BTC/USD"))
        mock_logging.debug.assert_called()


if __name__ == "__main__":
    unittest.main()
