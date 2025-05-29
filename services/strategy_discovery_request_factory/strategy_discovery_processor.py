"""
Stateless Strategy Discovery Processor.

This processor generates strategy discovery requests for specific timepoints
without maintaining any candle data state. The orchestrating service is responsible
for determining when and what timepoints to process.
"""

from datetime import datetime, timezone, timedelta
from typing import List
from absl import logging

from protos.discovery_pb2 import StrategyDiscoveryRequest, GAConfig
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp


class StrategyDiscoveryProcessor:
    """
    Stateless processor that generates strategy discovery requests for specific timepoints.
    
    No longer maintains candle deques or state - purely functional request generation.
    """
    
    def __init__(
        self,
        default_top_n: int,
        default_max_generations: int,
        default_population_size: int
    ):
        """
        Initialize the stateless strategy discovery processor.
        
        Args:
            default_top_n: Default number of top strategies to discover
            default_max_generations: Default GA max generations
            default_population_size: Default GA population size
        """
        self.default_top_n = default_top_n
        self.default_max_generations = default_max_generations
        self.default_population_size = default_population_size
        
        logging.info(
            f"StatelessProcessor initialized: "
            f"top_n={self.default_top_n}, "
            f"max_generations={self.default_max_generations}, "
            f"population_size={self.default_population_size}"
        )

    def _datetime_to_ms(self, dt: datetime) -> int:
        """Convert a datetime object to UTC milliseconds since epoch."""
        return int(dt.timestamp() * 1000)

    def generate_requests_for_timepoint(
        self,
        currency_pair: str,
        window_end_time_utc: datetime,
        fibonacci_windows_minutes: List[int]
    ) -> List[StrategyDiscoveryRequest]:
        """
        Generate strategy discovery requests for a specific timepoint.
        
        Args:
            currency_pair: The currency pair (e.g., "BTC/USD")
            window_end_time_utc: The end time for analysis windows
            fibonacci_windows_minutes: List of window sizes in minutes
            
        Returns:
            List of generated strategy discovery requests
        """
        generated_requests: List[StrategyDiscoveryRequest] = []
        window_end_time_ms = self._datetime_to_ms(window_end_time_utc)

        for window_minutes in sorted(fibonacci_windows_minutes):  # Ensure sorted if not already
            end_time_proto = Timestamp()
            end_time_proto.FromMilliseconds(window_end_time_ms)

            start_datetime_utc = window_end_time_utc - timedelta(minutes=window_minutes)
            start_time_proto = Timestamp()
            start_time_proto.FromDatetime(start_datetime_utc)

            strategy_types = [st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED]
            for strategy_type in strategy_types:
                request = StrategyDiscoveryRequest(
                    symbol=currency_pair,
                    start_time=start_time_proto,
                    end_time=end_time_proto,
                    strategy_type=strategy_type,
                    top_n=self.default_top_n,
                    ga_config=GAConfig(
                        max_generations=self.default_max_generations,
                        population_size=self.default_population_size,
                    )
                )
                generated_requests.append(request)
        
        if generated_requests:
            logging.info(
                f"StatelessProcessor generated {len(generated_requests)} requests for {currency_pair} "
                f"ending at {window_end_time_utc.isoformat()}"
            )
        return generated_requests
