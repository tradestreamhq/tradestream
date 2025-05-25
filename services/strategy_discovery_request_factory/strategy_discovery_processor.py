import collections
from datetime import datetime, timezone, timedelta
from absl import logging
from protos.marketdata_pb2 import Candle
from protos.discovery_pb2 import StrategyDiscoveryRequest, GAConfig
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp


class StrategyDiscoveryProcessor:
    def __init__(
        self,
        fibonacci_windows_minutes: list[int],
        deque_maxlen: int,
        default_top_n: int = 5,
        default_max_generations: int = 30,
        default_population_size: int = 50,
        candle_granularity_minutes: int = 1,
    ):
        self.fibonacci_windows_minutes = sorted(fibonacci_windows_minutes)
        self.deque_maxlen = deque_maxlen
        self.default_top_n = default_top_n
        self.default_max_generations = default_max_generations
        self.default_population_size = default_population_size
        self.candle_granularity_minutes = candle_granularity_minutes
        self.pair_deques: dict[str, collections.deque[Candle]] = {}
        logging.info(
            f"StrategyDiscoveryProcessor initialized with Fibonacci windows (minutes): {self.fibonacci_windows_minutes}, deque maxlen: {self.deque_maxlen}"
        )

    def initialize_deques(self, currency_pairs: list[str]):
        for pair in currency_pairs:
            if pair not in self.pair_deques:
                self.pair_deques[pair] = collections.deque(maxlen=self.deque_maxlen)
                logging.info(f"Initialized deque for currency pair: {pair}")

    def add_candle(self, candle: Candle) -> list[StrategyDiscoveryRequest]:
        currency_pair = candle.currency_pair
        if not currency_pair:
            logging.warning(f"Candle missing currency_pair: {candle.timestamp}")
            return []

        if currency_pair not in self.pair_deques:
            logging.warning(
                f"Received candle for uninitialized currency pair: {currency_pair}. Initializing deque."
            )
            self.initialize_deques([currency_pair])

        # Check for out-of-order candles
        if self.pair_deques[currency_pair]:
            last_candle_in_deque_ts_ms = (
                self.pair_deques[currency_pair][-1].timestamp.seconds * 1000
                + self.pair_deques[currency_pair][-1].timestamp.nanos // 1_000_000
            )
            new_candle_ts_ms = (
                candle.timestamp.seconds * 1000 + candle.timestamp.nanos // 1_000_000
            )
            if new_candle_ts_ms < last_candle_in_deque_ts_ms:
                logging.warning(
                    f"Received out-of-order candle for {currency_pair}. New: {new_candle_ts_ms}, Last in deque: {last_candle_in_deque_ts_ms}. Appending anyway."
                )

        self.pair_deques[currency_pair].append(candle)
        logging.debug(
            f"Added candle to {currency_pair} deque. New deque size: {len(self.pair_deques[currency_pair])}"
        )

        # Generate StrategyDiscoveryRequests
        generated_requests = []
        current_deque = list(self.pair_deques[currency_pair])

        # Convert candle timestamp to datetime for time calculations
        candle_timestamp = datetime.fromtimestamp(
            candle.timestamp.seconds + candle.timestamp.nanos / 1e9,
            tz=timezone.utc
        )

        for window_minutes in self.fibonacci_windows_minutes:
            # Convert window size from minutes to number of candles
            window_size_candles = window_minutes // self.candle_granularity_minutes
            if window_size_candles <= 0:  # Skip invalid window sizes
                logging.warning(
                    f"Skipping invalid Fibonacci window size (candles): {window_size_candles} for {window_minutes} minutes."
                )
                continue

            if len(current_deque) >= window_size_candles:
                # Calculate time range for this window
                end_time = Timestamp()
                end_time.FromDatetime(candle_timestamp)
                
                start_time_dt = candle_timestamp - timedelta(minutes=window_minutes)
                start_time = Timestamp()
                start_time.FromDatetime(start_time_dt)

                # Create GAConfig with default parameters
                ga_config = GAConfig(
                    max_generations=self.default_max_generations,
                    population_size=self.default_population_size
                )

                # Generate one request for each strategy type
                for strategy_type in StrategyType.values():
                    # Skip UNKNOWN strategy type
                    if strategy_type == StrategyType.UNKNOWN:
                        continue
                    
                    strategy_discovery_request = StrategyDiscoveryRequest(
                        symbol=currency_pair,
                        start_time=start_time,
                        end_time=end_time,
                        strategy_type=strategy_type,
                        top_n=self.default_top_n,
                        ga_config=ga_config
                    )
                    generated_requests.append(strategy_discovery_request)
                    logging.debug(
                        f"Generated StrategyDiscoveryRequest for {currency_pair}, window: {window_minutes} mins, strategy: {StrategyType.Name(strategy_type)}"
                    )
            else:
                logging.debug(
                    f"Not enough candles for {currency_pair} for window {window_minutes} mins ({window_size_candles} candles). Have {len(current_deque)}."
                )

        if generated_requests:
            logging.info(
                f"Generated {len(generated_requests)} StrategyDiscoveryRequests for {currency_pair} from new candle."
            )
        return generated_requests
