"""Unit tests for stateless strategy_discovery_processor module."""

import unittest
from datetime import datetime, timezone, timedelta

from protos.discovery_pb2 import StrategyDiscoveryRequest
from protos.strategies_pb2 import StrategyType

from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)


class StatelessStrategyDiscoveryProcessorTest(unittest.TestCase):
    """Test stateless strategy discovery processor functionality."""

    def setUp(self):
        """Set up test environment."""
        self.default_top_n = 3
        self.default_max_generations = 10
        self.default_population_size = 20

    def test_initialization(self):
        """Test processor initialization."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=self.default_top_n,
            default_max_generations=self.default_max_generations,
            default_population_size=self.default_population_size,
        )

        self.assertEqual(processor.default_top_n, self.default_top_n)
        self.assertEqual(
            processor.default_max_generations, self.default_max_generations
        )
        self.assertEqual(
            processor.default_population_size, self.default_population_size
        )

    def test_datetime_to_ms(self):
        """Test datetime to milliseconds conversion."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=5,
            default_max_generations=30,
            default_population_size=50,
        )

        # Test known datetime
        test_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expected_ms = int(test_dt.timestamp() * 1000)
        actual_ms = processor._datetime_to_ms(test_dt)

        self.assertEqual(actual_ms, expected_ms)

    def test_generate_requests_empty_windows(self):
        """Test generating requests with empty fibonacci windows."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=5,
            default_max_generations=30,
            default_population_size=50,
        )

        end_time = datetime.now(timezone.utc)
        requests = processor.generate_requests_for_timepoint(
            currency_pair="BTC/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=[],
        )

        self.assertEqual(len(requests), 0)

    def test_generate_requests_single_window(self):
        """Test generating requests for a single window."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=5,
            default_max_generations=30,
            default_population_size=50,
        )

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [60]  # 1 hour window

        requests = processor.generate_requests_for_timepoint(
            currency_pair="BTC/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        # Number of strategy types (excluding UNSPECIFIED)
        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]
        expected_count = len(expected_strategy_types)

        self.assertEqual(len(requests), expected_count)

        # Verify request structure
        for request in requests:
            self.assertEqual(request.symbol, "BTC/USD")
            self.assertNotEqual(request.strategy_type, StrategyType.UNSPECIFIED)
            self.assertGreater(request.end_time.seconds, request.start_time.seconds)
            self.assertEqual(request.top_n, 5)
            self.assertEqual(request.ga_config.max_generations, 30)
            self.assertEqual(request.ga_config.population_size, 50)

    def test_generate_requests_multiple_windows(self):
        """Test generating requests for multiple windows."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=3,
            default_max_generations=20,
            default_population_size=40,
        )

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [30, 60, 120]  # 30min, 1hr, 2hr windows

        requests = processor.generate_requests_for_timepoint(
            currency_pair="ETH/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]
        expected_count = len(fibonacci_windows) * len(expected_strategy_types)

        self.assertEqual(len(requests), expected_count)

        # Verify we have requests for all windows
        unique_durations = set()
        for request in requests:
            duration_minutes = (
                request.end_time.seconds - request.start_time.seconds
            ) // 60
            unique_durations.add(duration_minutes)

        self.assertEqual(sorted(unique_durations), sorted(fibonacci_windows))

    def test_generate_requests_time_windows_accurate(self):
        """Test that time windows are calculated accurately."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=10,
            default_population_size=20,
        )

        # Use a specific end time for predictable testing
        end_time = datetime(2023, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        fibonacci_windows = [60]  # 1 hour window

        requests = processor.generate_requests_for_timepoint(
            currency_pair="BTC/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        self.assertGreater(len(requests), 0)

        # Check the first request's timing
        request = requests[0]

        # End time should match our input
        end_time_ms = int(end_time.timestamp() * 1000)
        self.assertEqual(request.end_time.ToMilliseconds(), end_time_ms)

        # Start time should be 60 minutes before end time
        expected_start_time = end_time - timedelta(minutes=60)
        expected_start_ms = int(expected_start_time.timestamp() * 1000)
        self.assertEqual(request.start_time.ToMilliseconds(), expected_start_ms)

    def test_generate_requests_unsorted_windows(self):
        """Test that unsorted fibonacci windows are handled correctly."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=2,
            default_max_generations=15,
            default_population_size=30,
        )

        end_time = datetime.now(timezone.utc)
        # Provide unsorted windows
        fibonacci_windows = [120, 30, 90, 60]

        requests = processor.generate_requests_for_timepoint(
            currency_pair="ADA/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        # Should still generate requests for all windows
        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]
        expected_count = len(fibonacci_windows) * len(expected_strategy_types)

        self.assertEqual(len(requests), expected_count)

    def test_generate_requests_different_currency_pairs(self):
        """Test generating requests for different currency pairs."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=5,
            default_population_size=10,
        )

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [30]

        pairs_to_test = ["BTC/USD", "ETH/USD", "ADA/USD"]

        for pair in pairs_to_test:
            with self.subTest(currency_pair=pair):
                requests = processor.generate_requests_for_timepoint(
                    currency_pair=pair,
                    window_end_time_utc=end_time,
                    fibonacci_windows_minutes=fibonacci_windows,
                )

                self.assertGreater(len(requests), 0)

                # All requests should have the correct symbol
                for request in requests:
                    self.assertEqual(request.symbol, pair)

    def test_generate_requests_ga_config_values(self):
        """Test that GA configuration values are correctly set."""
        top_n = 7
        max_generations = 25
        population_size = 75

        processor = StrategyDiscoveryProcessor(
            default_top_n=top_n,
            default_max_generations=max_generations,
            default_population_size=population_size,
        )

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [45]

        requests = processor.generate_requests_for_timepoint(
            currency_pair="SOL/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        self.assertGreater(len(requests), 0)

        # Verify all requests have correct GA config
        for request in requests:
            self.assertEqual(request.top_n, top_n)
            self.assertEqual(request.ga_config.max_generations, max_generations)
            self.assertEqual(request.ga_config.population_size, population_size)

    def test_all_strategy_types_included(self):
        """Test that all strategy types (except UNSPECIFIED) are included."""
        processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=10,
            default_population_size=20,
        )

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [60]

        requests = processor.generate_requests_for_timepoint(
            currency_pair="BTC/USD",
            window_end_time_utc=end_time,
            fibonacci_windows_minutes=fibonacci_windows,
        )

        # Get all strategy types from requests
        request_strategy_types = {request.strategy_type for request in requests}

        # Get expected strategy types
        expected_strategy_types = {
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        }

        self.assertEqual(request_strategy_types, expected_strategy_types)

        # Ensure UNSPECIFIED is not included
        for request in requests:
            self.assertNotEqual(request.strategy_type, StrategyType.UNSPECIFIED)


if __name__ == "__main__":
    unittest.main()
