"""Integration tests for stateless strategy_discovery_request_factory."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from protos.discovery_pb2 import StrategyDiscoveryRequest
from protos.strategies_pb2 import StrategyType

from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.persistence.influxdb_last_processed_tracker import (
    InfluxDBLastProcessedTracker,
)


class StatelessIntegrationTest(unittest.TestCase):
    """Integration tests for stateless component interactions."""

    def setUp(self):
        """Set up test environment with mocked external services."""
        # Mock Kafka producer
        self.mock_kafka_producer = patch(
            "services.strategy_discovery_request_factory.kafka_publisher.kafka.KafkaProducer"
        ).start()

        # Mock InfluxDB tracker
        self.mock_tracker_class = patch(
            "shared.persistence.influxdb_last_processed_tracker.InfluxDBLastProcessedTracker"
        ).start()

        # Set up mock instances
        self.mock_producer_instance = Mock()
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        self.mock_producer_instance.send.return_value = mock_future
        self.mock_kafka_producer.return_value = self.mock_producer_instance

        self.mock_tracker_instance = Mock(spec=InfluxDBLastProcessedTracker)
        self.mock_tracker_instance.client = Mock()  # Ensure client exists
        self.mock_tracker_class.return_value = self.mock_tracker_instance

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()

    def test_stateless_processor_kafka_publisher_integration(self):
        """Test integration between stateless processor and Kafka publisher."""
        # Set up components
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=3,
            default_max_generations=20,
            default_population_size=40,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        # Generate requests using stateless processor
        currency_pair = "BTC/USD"
        end_time = datetime(2023, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        fibonacci_windows = [60, 120]  # 1 hour and 2 hour windows

        discovery_requests = strategy_processor.generate_requests_for_timepoint(
            currency_pair, end_time, fibonacci_windows
        )

        # Verify requests were generated
        expected_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]
        expected_request_count = len(fibonacci_windows) * len(expected_strategy_types)
        self.assertEqual(len(discovery_requests), expected_request_count)

        # Publish all requests
        total_published = 0
        for request in discovery_requests:
            kafka_publisher.publish_request(request, currency_pair)
            total_published += 1

        # Verify Kafka publishing
        self.assertEqual(total_published, expected_request_count)
        self.assertEqual(
            self.mock_producer_instance.send.call_count, expected_request_count
        )

    def test_processor_generates_valid_requests_for_kafka(self):
        """Test that processor generates valid requests that can be published to Kafka."""
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=5,
            default_max_generations=30,
            default_population_size=50,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        # Generate requests for multiple currency pairs
        currency_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]
        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [30, 60, 90]

        all_requests = []
        for pair in currency_pairs:
            requests = strategy_processor.generate_requests_for_timepoint(
                pair, end_time, fibonacci_windows
            )
            all_requests.extend(requests)

        # Verify all requests have required fields for Kafka publishing
        for request in all_requests:
            self.assertIsInstance(request, StrategyDiscoveryRequest)
            self.assertIn(request.symbol, currency_pairs)
            self.assertNotEqual(request.strategy_type, StrategyType.UNSPECIFIED)
            self.assertGreater(request.end_time.seconds, request.start_time.seconds)
            self.assertEqual(request.top_n, 5)
            self.assertEqual(request.ga_config.max_generations, 30)
            self.assertEqual(request.ga_config.population_size, 50)

        # Publish all requests
        for request in all_requests:
            kafka_publisher.publish_request(request, request.symbol)

        # Verify all were published
        self.assertEqual(self.mock_producer_instance.send.call_count, len(all_requests))

    def test_processor_with_different_configurations(self):
        """Test processor with different configurations generates appropriate requests."""
        # Test with minimal configuration
        minimal_processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=5,
            default_population_size=10,
        )

        # Test with maximal configuration
        maximal_processor = StrategyDiscoveryProcessor(
            default_top_n=10,
            default_max_generations=100,
            default_population_size=200,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [60]
        currency_pair = "BTC/USD"

        # Generate requests with both configurations
        minimal_requests = minimal_processor.generate_requests_for_timepoint(
            currency_pair, end_time, fibonacci_windows
        )

        maximal_requests = maximal_processor.generate_requests_for_timepoint(
            currency_pair, end_time, fibonacci_windows
        )

        # Both should generate same number of requests (one per strategy type)
        self.assertEqual(len(minimal_requests), len(maximal_requests))

        # But with different GA configurations
        for request in minimal_requests:
            self.assertEqual(request.top_n, 1)
            self.assertEqual(request.ga_config.max_generations, 5)
            self.assertEqual(request.ga_config.population_size, 10)

        for request in maximal_requests:
            self.assertEqual(request.top_n, 10)
            self.assertEqual(request.ga_config.max_generations, 100)
            self.assertEqual(request.ga_config.population_size, 200)

        # Both should be publishable
        for request in minimal_requests + maximal_requests:
            kafka_publisher.publish_request(request, currency_pair)

        self.assertEqual(
            self.mock_producer_instance.send.call_count,
            len(minimal_requests) + len(maximal_requests),
        )

    def test_processor_time_window_accuracy(self):
        """Test that processor generates accurate time windows for requests."""
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=10,
            default_population_size=20,
        )

        # Use specific times for predictable testing
        end_time = datetime(2023, 7, 15, 10, 30, 0, tzinfo=timezone.utc)
        fibonacci_windows = [60, 120, 180]  # 1hr, 2hr, 3hr

        requests = strategy_processor.generate_requests_for_timepoint(
            "ETH/USD", end_time, fibonacci_windows
        )

        # Group requests by window duration
        requests_by_window = {}
        for request in requests:
            duration_minutes = (
                request.end_time.seconds - request.start_time.seconds
            ) // 60
            if duration_minutes not in requests_by_window:
                requests_by_window[duration_minutes] = []
            requests_by_window[duration_minutes].append(request)

        # Verify each window has correct timing
        for window_minutes in fibonacci_windows:
            self.assertIn(window_minutes, requests_by_window)
            window_requests = requests_by_window[window_minutes]

            for request in window_requests:
                # Verify end time
                end_time_ms = int(end_time.timestamp() * 1000)
                self.assertEqual(request.end_time.ToMilliseconds(), end_time_ms)

                # Verify start time
                expected_start_time = end_time.timestamp() - (window_minutes * 60)
                expected_start_ms = int(expected_start_time * 1000)
                self.assertEqual(request.start_time.ToMilliseconds(), expected_start_ms)

    def test_kafka_serialization_integration(self):
        """Test that generated requests can be properly serialized for Kafka."""
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=2,
            default_max_generations=15,
            default_population_size=30,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [45]

        requests = strategy_processor.generate_requests_for_timepoint(
            "SOL/USD", end_time, fibonacci_windows
        )

        # Test serialization by attempting to publish
        for request in requests:
            # This should not raise any serialization errors
            kafka_publisher.publish_request(request, "SOL/USD")

        # Verify Kafka send was called with serialized data
        for call in self.mock_producer_instance.send.call_args_list:
            call_kwargs = call[1]

            # Verify value is bytes (serialized protobuf)
            self.assertIsInstance(call_kwargs["value"], bytes)

            # Verify key is bytes (encoded string)
            self.assertIsInstance(call_kwargs["key"], bytes)
            self.assertEqual(call_kwargs["key"], b"SOL/USD")

    def test_error_handling_integration(self):
        """Test error handling across integrated components."""
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=5,
            default_population_size=10,
        )

        # Mock Kafka producer to fail on send
        self.mock_producer_instance.send.side_effect = Exception("Kafka send failed")

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [30]

        requests = strategy_processor.generate_requests_for_timepoint(
            "ADA/USD", end_time, fibonacci_windows
        )

        # Processor should still generate requests despite Kafka issues
        self.assertGreater(len(requests), 0)

        # Publishing should handle errors gracefully (not raise)
        for request in requests:
            # Should not raise exception due to retry/error handling
            kafka_publisher.publish_request(request, "ADA/USD")

    def test_multiple_processors_same_kafka_publisher(self):
        """Test multiple processors sharing the same Kafka publisher."""
        processor1 = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=10,
            default_population_size=20,
        )

        processor2 = StrategyDiscoveryProcessor(
            default_top_n=5,
            default_max_generations=50,
            default_population_size=100,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        end_time = datetime.now(timezone.utc)
        fibonacci_windows = [60]

        # Generate requests from both processors
        requests1 = processor1.generate_requests_for_timepoint(
            "BTC/USD", end_time, fibonacci_windows
        )

        requests2 = processor2.generate_requests_for_timepoint(
            "ETH/USD", end_time, fibonacci_windows
        )

        # Publish all requests through same publisher
        all_requests = requests1 + requests2
        for request in all_requests:
            kafka_publisher.publish_request(request, request.symbol)

        # Verify all were published
        self.assertEqual(self.mock_producer_instance.send.call_count, len(all_requests))

        # Verify different configurations were preserved
        btc_requests = [r for r in all_requests if r.symbol == "BTC/USD"]
        eth_requests = [r for r in all_requests if r.symbol == "ETH/USD"]

        for request in btc_requests:
            self.assertEqual(request.top_n, 1)
            self.assertEqual(request.ga_config.max_generations, 10)

        for request in eth_requests:
            self.assertEqual(request.top_n, 5)
            self.assertEqual(request.ga_config.max_generations, 50)

    def test_component_cleanup_integration(self):
        """Test proper cleanup of integrated components."""
        strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=1,
            default_max_generations=10,
            default_population_size=20,
        )

        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        # Use components
        end_time = datetime.now(timezone.utc)
        requests = strategy_processor.generate_requests_for_timepoint(
            "BTC/USD", end_time, [60]
        )

        for request in requests:
            kafka_publisher.publish_request(request, "BTC/USD")

        # Clean up
        kafka_publisher.close()

        # Verify cleanup
        self.mock_producer_instance.flush.assert_called_once()
        self.mock_producer_instance.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
