"""Unit tests for strategy_discovery_processor module."""

import unittest
from unittest.mock import patch
import collections
from protos.strategies_pb2 import StrategyType
from google.protobuf import any_pb2
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.test_utils import (
    create_test_candle,
    create_test_candles,
    get_candle_timestamp_ms,
)


class StrategyDiscoveryProcessorTest(unittest.TestCase):
    """Test candle processing functionality."""

    def setUp(self):
        """Set up test environment."""
        self.fibonacci_windows = [5, 8, 13, 21]  # Small windows for testing
        self.deque_maxlen = 50
        self.default_top_n = 3
        self.default_max_generations = 10
        self.default_population_size = 20
        self.candle_granularity_minutes = 1

        self.processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=self.fibonacci_windows,
            deque_maxlen=self.deque_maxlen,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=self.candle_granularity_minutes,
        )

    def test_initialization(self):
        """Test StrategyDiscoveryProcessor initialization."""
        self.assertEqual(self.processor.fibonacci_windows_minutes, [5, 8, 13, 21])
        self.assertEqual(self.processor.deque_maxlen, self.deque_maxlen)
        self.assertEqual(self.processor.default_top_n, self.default_top_n)
        self.assertEqual(
            self.processor.default_max_generations, self.default_max_generations
        )
        self.assertEqual(
            self.processor.default_population_size, self.default_population_size
        )
        self.assertEqual(
            self.processor.candle_granularity_minutes, self.candle_granularity_minutes
        )
        self.assertIsInstance(self.processor.pair_deques, dict)
        self.assertEqual(len(self.processor.pair_deques), 0)

    def test_fibonacci_windows_sorted(self):
        """Test that Fibonacci windows are sorted during initialization."""
        unsorted_windows = [21, 5, 13, 8]
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=unsorted_windows,
            deque_maxlen=50,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=self.candle_granularity_minutes,
        )

        self.assertEqual(processor.fibonacci_windows_minutes, [5, 8, 13, 21])

    def test_initialize_deques(self):
        """Test deque initialization for currency pairs."""
        currency_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]

        self.processor.initialize_deques(currency_pairs)

        for pair in currency_pairs:
            self.assertIn(pair, self.processor.pair_deques)
            self.assertIsInstance(self.processor.pair_deques[pair], collections.deque)
            self.assertEqual(self.processor.pair_deques[pair].maxlen, self.deque_maxlen)
            self.assertEqual(len(self.processor.pair_deques[pair]), 0)

    def test_initialize_deques_already_exists(self):
        """Test that existing deques are not overwritten."""
        currency_pairs = ["BTC/USD"]

        # Initialize first time
        self.processor.initialize_deques(currency_pairs)
        original_deque = self.processor.pair_deques["BTC/USD"]

        # Add a candle to the deque
        test_candle = create_test_candle("BTC/USD")
        original_deque.append(test_candle)

        # Initialize again
        self.processor.initialize_deques(currency_pairs)

        # Should be the same deque with the candle still there
        self.assertIs(self.processor.pair_deques["BTC/USD"], original_deque)
        self.assertEqual(len(self.processor.pair_deques["BTC/USD"]), 1)

    def test_add_candle_missing_currency_pair(self):
        """Test handling of candle with missing currency pair."""
        candle = create_test_candle("")  # Empty currency pair

        requests = self.processor.add_candle(candle)

        self.assertEqual(len(requests), 0)
        self.assertEqual(len(self.processor.pair_deques), 0)

    def test_add_candle_uninitialized_pair(self):
        """Test adding candle for uninitialized currency pair."""
        candle = create_test_candle("BTC/USD")

        requests = self.processor.add_candle(candle)

        # Should automatically initialize the deque
        self.assertIn("BTC/USD", self.processor.pair_deques)
        self.assertEqual(len(self.processor.pair_deques["BTC/USD"]), 1)

        # Should not generate requests yet (need more candles)
        self.assertEqual(len(requests), 0)

    def test_add_candle_insufficient_candles(self):
        """Test adding candles when insufficient for any window."""
        currency_pair = "BTC/USD"
        self.processor.initialize_deques([currency_pair])

        # Add only 3 candles (less than smallest window of 5)
        for i in range(3):
            candle = create_test_candle(
                currency_pair, timestamp_ms=1640995200000 + i * 60000
            )
            requests = self.processor.add_candle(candle)
            self.assertEqual(len(requests), 0)

        self.assertEqual(len(self.processor.pair_deques[currency_pair]), 3)

    def test_add_candle_generates_requests(self):
        """Test that adding candles generates strategy discovery requests."""
        currency_pair = "BTC/USD"
        self.processor.initialize_deques([currency_pair])
        num_strategy_types = len(
            [st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED]
        )

        # Add enough candles for smallest window (5)
        candles = create_test_candles(5, currency_pair)
        requests_list = []

        for candle in candles:
            requests = self.processor.add_candle(candle)
            requests_list.extend(requests)

        # Should generate requests for the 5-minute window for each strategy type when 5th candle is added
        self.assertEqual(len(requests_list), 1 * num_strategy_types)

        # Verify request structure
        for request in requests_list:
            self.assertEqual(request.symbol, currency_pair)
            self.assertNotEqual(request.strategy_type, StrategyType.UNSPECIFIED)
            self.assertGreater(request.end_time.seconds, request.start_time.seconds)
            self.assertEqual(request.top_n, self.default_top_n)
            self.assertEqual(
                request.ga_config.max_generations, self.default_max_generations
            )
            self.assertEqual(
                request.ga_config.population_size, self.default_population_size
            )

    def test_add_candle_multiple_windows(self):
        """Test generating requests for multiple Fibonacci windows."""
        currency_pair = "BTC/USD"
        self.processor.initialize_deques([currency_pair])
        num_strategy_types = len(
            [st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED]
        )

        # Add enough candles for multiple windows (21 candles)
        candles = create_test_candles(21, currency_pair)
        all_requests = []

        for candle in candles:
            requests = self.processor.add_candle(candle)
            all_requests.extend(requests)

        # When 21st candle is added, should generate requests for all windows (5, 8, 13, 21)
        # The add_candle for the 21st candle itself will trigger these.
        final_add_requests = self.processor.add_candle(candles[-1])

        self.assertEqual(
            len(final_add_requests), 4 * num_strategy_types
        )  # All 4 windows * number of strategy types

        # Verify window time ranges
        request_window_durations_minutes = sorted(
            list(
                set(
                    (req.end_time.seconds - req.start_time.seconds) // 60
                    for req in final_add_requests
                )
            )
        )
        # Convert fibonacci windows from minutes to candle counts, then to minutes again for comparison
        # This is a bit indirect, but checks the effective window duration.
        expected_durations = sorted([win for win in self.fibonacci_windows])

        # Note: The request start_time and end_time reflect the window duration,
        # not the number of candles in the request.
        # The number of candles in the request will be window_minutes / candle_granularity_minutes.
        # Here we verify the duration implied by start_time and end_time.
        self.assertEqual(len(request_window_durations_minutes), len(expected_durations))
        for i in range(len(expected_durations)):
            # Allow for slight discrepancies due to integer division if granularity > 1
            self.assertAlmostEqual(
                request_window_durations_minutes[i],
                expected_durations[i],
                delta=self.candle_granularity_minutes,
            )

    def test_add_candle_out_of_order_warning(self):
        """Test warning for out-of-order candles."""
        currency_pair = "BTC/USD"
        self.processor.initialize_deques([currency_pair])

        # Add first candle
        candle1 = create_test_candle(
            currency_pair, timestamp_ms=1640995260000
        )  # Later time
        self.processor.add_candle(candle1)

        # Add second candle with earlier timestamp
        candle2 = create_test_candle(
            currency_pair, timestamp_ms=1640995200000
        )  # Earlier time

        with patch(
            "services.strategy_discovery_request_factory.strategy_discovery_processor.logging"
        ) as mock_logging:
            self.processor.add_candle(candle2)
            mock_logging.warning.assert_called()

    def test_add_candle_deque_maxlen_behavior(self):
        """Test that deque respects maxlen."""
        # Create processor with small maxlen
        small_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=10,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=self.candle_granularity_minutes,
        )

        currency_pair = "BTC/USD"
        small_processor.initialize_deques([currency_pair])

        # Add more candles than maxlen
        candles = create_test_candles(15, currency_pair)
        for candle in candles:
            small_processor.add_candle(candle)

        # Deque should only contain last 10 candles
        self.assertEqual(len(small_processor.pair_deques[currency_pair]), 10)

        # Verify it contains the most recent candles
        deque_candles = list(small_processor.pair_deques[currency_pair])
        expected_timestamps = [get_candle_timestamp_ms(c) for c in candles[-10:]]
        actual_timestamps = [get_candle_timestamp_ms(c) for c in deque_candles]
        self.assertEqual(actual_timestamps, expected_timestamps)

    def test_window_size_calculation(self):
        """Test conversion from minutes to candle count."""
        # Test with different granularities
        processor_5min = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[10, 15],  # 10 and 15 minutes
            deque_maxlen=50,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=5,  # 5-minute candles
        )
        num_strategy_types = len(
            [st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED]
        )

        currency_pair = "BTC/USD"
        processor_5min.initialize_deques([currency_pair])

        # Add 3 candles (15 minutes total with 5-minute granularity)
        # Window 10min = 2 candles, Window 15min = 3 candles
        candles = create_test_candles(3, currency_pair)
        requests = []
        for candle in candles:
            req = processor_5min.add_candle(candle)
            requests.extend(req)

        # The last add_candle (3rd candle) should trigger requests for both windows
        final_add_requests = processor_5min.add_candle(candles[-1])
        self.assertEqual(
            len(final_add_requests), 2 * num_strategy_types
        )  # (10min window + 15min window) * num_types

        # Check the implied window durations from the requests
        request_window_durations_minutes = sorted(
            list(
                set(
                    (req.end_time.seconds - req.start_time.seconds) // 60
                    for req in final_add_requests
                )
            )
        )
        # The fibonacci_windows_minutes are [10, 15]
        # These should be the durations reflected in the start_time and end_time of the requests.
        self.assertEqual(request_window_durations_minutes, [10, 15])

    def test_invalid_window_size_skip(self):
        """Test that invalid window sizes are skipped."""
        # Create processor with window smaller than granularity
        processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[0, -1],  # Invalid windows
            deque_maxlen=50,
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
            candle_granularity_minutes=1,
        )

        currency_pair = "BTC/USD"
        processor.initialize_deques([currency_pair])

        candle = create_test_candle(currency_pair)

        with patch(
            "services.strategy_discovery_request_factory.strategy_discovery_processor.logging"
        ) as mock_logging:
            requests = processor.add_candle(candle)

            # Should log warning about invalid windows
            mock_logging.warning.assert_called()

            # Should not generate any requests
            self.assertEqual(len(requests), 0)

    @patch(
        "services.strategy_discovery_request_factory.strategy_discovery_processor.logging"
    )
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        currency_pair = "BTC/USD"

        # Test initialization logging
        self.processor.initialize_deques([currency_pair])
        mock_logging.info.assert_called()

        # Test candle addition logging
        candle = create_test_candle(currency_pair)
        self.processor.add_candle(candle)
        mock_logging.debug.assert_called()


if __name__ == "__main__":
    unittest.main()
