"""
Strategy Discovery Processor with integrated InfluxDB timestamp tracking.

This processor maintains candle deques for different currency pairs and generates
strategy discovery requests when sufficient candles are available for each Fibonacci window.
It integrates directly with InfluxDBLastProcessedTracker for state management.
"""

import collections
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from absl import logging

from protos.marketdata_pb2 import Candle
from protos.discovery_pb2 import StrategyDiscoveryRequest, GAConfig
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker


class StrategyDiscoveryProcessor:
    """
    Processes candles and generates strategy discovery requests for different time windows.
    
    Integrates with InfluxDBLastProcessedTracker to maintain state across runs.
    """
    
    def __init__(
        self,
        fibonacci_windows_minutes: List[int],
        deque_maxlen: int,
        default_top_n: int = 5,
        default_max_generations: int = 30,
        default_population_size: int = 50,
        candle_granularity_minutes: int = 1,
        tracker: Optional[InfluxDBLastProcessedTracker] = None,
        service_identifier: str = "strategy_discovery_processor"
    ):
        """
        Initialize the strategy discovery processor.
        
        Args:
            fibonacci_windows_minutes: List of Fibonacci window sizes in minutes
            deque_maxlen: Maximum length of candle deques
            default_top_n: Default number of top strategies to discover
            default_max_generations: Default GA max generations
            default_population_size: Default GA population size  
            candle_granularity_minutes: Granularity of candles in minutes
            tracker: InfluxDB tracker for state persistence (optional)
            service_identifier: Service identifier for tracker
        """
        self.fibonacci_windows_minutes = sorted(fibonacci_windows_minutes)
        self.deque_maxlen = deque_maxlen
        self.default_top_n = default_top_n
        self.default_max_generations = default_max_generations
        self.default_population_size = default_population_size
        self.candle_granularity_minutes = candle_granularity_minutes
        self.tracker = tracker
        self.service_identifier = service_identifier
        
        # Candle deques per currency pair
        self.pair_deques: Dict[str, collections.deque[Candle]] = {}
        
        # Track last processed timestamps per pair
        self.last_processed_timestamps: Dict[str, int] = {}
        
        logging.info(
            f"StrategyDiscoveryProcessor initialized: "
            f"windows={self.fibonacci_windows_minutes}, "
            f"deque_maxlen={self.deque_maxlen}, "
            f"granularity={self.candle_granularity_minutes}min"
        )

    def initialize_pair(self, currency_pair: str) -> None:
        """Initialize deque and load state for a currency pair."""
        if currency_pair not in self.pair_deques:
            self.pair_deques[currency_pair] = collections.deque(maxlen=self.deque_maxlen)
            logging.info(f"Initialized deque for {currency_pair}")
        
        # Load last processed timestamp if tracker is available
        if self.tracker and currency_pair not in self.last_processed_timestamps:
            last_ts = self.tracker.get_last_processed_timestamp(
                self.service_identifier, 
                currency_pair
            )
            self.last_processed_timestamps[currency_pair] = last_ts or 0
            logging.info(f"Loaded last timestamp for {currency_pair}: {last_ts}")

    def initialize_pairs(self, currency_pairs: List[str]) -> None:
        """Initialize multiple currency pairs."""
        for pair in currency_pairs:
            self.initialize_pair(pair)

    def add_candle(self, candle: Candle) -> List[StrategyDiscoveryRequest]:
        """
        Add a candle and generate strategy discovery requests if conditions are met.
        
        Args:
            candle: The candle to add
            
        Returns:
            List of generated strategy discovery requests
        """
        currency_pair = candle.currency_pair
        if not currency_pair:
            logging.warning("Candle missing currency_pair, skipping")
            return []

        # Initialize pair if needed
        if currency_pair not in self.pair_deques:
            self.initialize_pair(currency_pair)

        # Get candle timestamp
        candle_ts_ms = self._get_candle_timestamp_ms(candle)
        
        # Check if this candle is newer than our last processed
        last_processed = self.last_processed_timestamps.get(currency_pair, 0)
        if candle_ts_ms <= last_processed:
            logging.debug(
                f"Skipping old candle for {currency_pair}: "
                f"{candle_ts_ms} <= {last_processed}"
            )
            return []

        # Add candle to deque
        self.pair_deques[currency_pair].append(candle)
        
        # Update timestamp tracking
        self.last_processed_timestamps[currency_pair] = candle_ts_ms
        if self.tracker:
            self.tracker.update_last_processed_timestamp(
                self.service_identifier,
                currency_pair, 
                candle_ts_ms
            )

        logging.debug(
            f"Added candle for {currency_pair} at {candle_ts_ms}, "
            f"deque size: {len(self.pair_deques[currency_pair])}"
        )

        # Generate discovery requests
        return self._generate_discovery_requests(candle)

    def _get_candle_timestamp_ms(self, candle: Candle) -> int:
        """Get timestamp in milliseconds from candle."""
        return candle.timestamp.seconds * 1000 + candle.timestamp.nanos // 1_000_000

    def _generate_discovery_requests(self, candle: Candle) -> List[StrategyDiscoveryRequest]:
        """Generate strategy discovery requests for the given candle."""
        currency_pair = candle.currency_pair
        current_deque = self.pair_deques[currency_pair]
        
        if not current_deque:
            return []

        generated_requests = []
        candle_timestamp = datetime.fromtimestamp(
            candle.timestamp.seconds + candle.timestamp.nanos / 1e9, 
            tz=timezone.utc
        )

        # Generate requests for each Fibonacci window
        for window_minutes in self.fibonacci_windows_minutes:
            window_size_candles = window_minutes // self.candle_granularity_minutes
            
            if window_size_candles <= 0:
                logging.warning(f"Invalid window size: {window_minutes} minutes")
                continue
                
            if len(current_deque) < window_size_candles:
                logging.debug(
                    f"Insufficient candles for {currency_pair} window {window_minutes}min: "
                    f"need {window_size_candles}, have {len(current_deque)}"
                )
                continue

            # Create time range for window
            end_time = Timestamp()
            end_time.FromDatetime(candle_timestamp)
            
            start_time_dt = candle_timestamp - timedelta(minutes=window_minutes)
            start_time = Timestamp()
            start_time.FromDatetime(start_time_dt)
            
            # Generate requests for each strategy type
            strategy_types = [st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED]
            
            for strategy_type in strategy_types:
                request = StrategyDiscoveryRequest(
                    symbol=currency_pair,
                    start_time=start_time,
                    end_time=end_time,
                    strategy_type=strategy_type,
                    top_n=self.default_top_n,
                    ga_config=GAConfig(
                        max_generations=self.default_max_generations,
                        population_size=self.default_population_size,
                    )
                )
                generated_requests.append(request)
                
                logging.debug(
                    f"Generated request: {currency_pair}, {window_minutes}min, "
                    f"{StrategyType.Name(strategy_type)}"
                )

        if generated_requests:
            logging.info(
                f"Generated {len(generated_requests)} discovery requests for {currency_pair}"
            )
            
        return generated_requests

    def get_deque_status(self) -> Dict[str, int]:
        """Get the current size of each currency pair's deque."""
        return {pair: len(deque) for pair, deque in self.pair_deques.items()}

    def get_last_processed_timestamps(self) -> Dict[str, int]:
        """Get the last processed timestamp for each currency pair."""
        return self.last_processed_timestamps.copy()

    def close(self) -> None:
        """Clean up resources."""
        self.pair_deques.clear()
        self.last_processed_timestamps.clear()
        logging.info("StrategyDiscoveryProcessor closed")
