import collections
from absl import logging
from protos.marketdata_pb2 import Candle
from protos.backtesting_pb2 import BacktestRequest
from protos.strategies_pb2 import Strategy, StrategyType
from google.protobuf import any_pb2



class CandleProcessor:
    def __init__(
        self,
        fibonacci_windows_minutes: list[int],
        deque_maxlen: int,
        default_strategy_type: StrategyType,
        default_strategy_parameters_any: any_pb2.Any = None,
        candle_granularity_minutes: int = 1,
    ):
        self.fibonacci_windows_minutes = sorted(fibonacci_windows_minutes)
        self.deque_maxlen = deque_maxlen
        self.default_strategy_type = default_strategy_type
        self.default_strategy_parameters_any = (
            default_strategy_parameters_any or any_pb2.Any()
        )
        self.candle_granularity_minutes = candle_granularity_minutes
        self.pair_deques: dict[str, collections.deque[Candle]] = {}
        logging.info(
            f"CandleProcessor initialized with Fibonacci windows (minutes): {self.fibonacci_windows_minutes}, deque maxlen: {self.deque_maxlen}"
        )

    def initialize_deques(self, currency_pairs: list[str]):
        for pair in currency_pairs:
            if pair not in self.pair_deques:
                self.pair_deques[pair] = collections.deque(maxlen=self.deque_maxlen)
                logging.info(f"Initialized deque for currency pair: {pair}")

    def add_candle(self, candle: Candle) -> list[BacktestRequest]:
        currency_pair = candle.currency_pair
        if not currency_pair:
            logging.warning(f"Candle missing currency_pair: {candle.timestamp}")
            return []

        if currency_pair not in self.pair_deques:
            logging.warning(
                f"Received candle for uninitialized currency pair: {currency_pair}. Initializing deque."
            )
            self.initialize_deques([currency_pair])

        # Ensure candles are added in order if possible (though deque itself doesn't enforce internal order)
        # If deque is not empty and new candle is older, log warning. This indicates issue upstream or with polling.
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

        generated_requests = []
        current_deque = list(
            self.pair_deques[currency_pair]
        )  # Work with a copy for windowing

        for window_minutes in self.fibonacci_windows_minutes:
            # Convert window size from minutes to number of candles
            window_size_candles = window_minutes // self.candle_granularity_minutes
            if window_size_candles <= 0:  # Skip invalid window sizes
                logging.warning(
                    f"Skipping invalid Fibonacci window size (candles): {window_size_candles} for {window_minutes} minutes."
                )
                continue

            if len(current_deque) >= window_size_candles:
                # Extract the most recent `window_size_candles` candles
                window_candles = current_deque[-window_size_candles:]

                strategy_msg = Strategy(
                    type=self.default_strategy_type,
                    parameters=self.default_strategy_parameters_any,
                )
                backtest_request = BacktestRequest(
                    candles=window_candles, strategy=strategy_msg
                )
                generated_requests.append(backtest_request)
                logging.debug(
                    f"Generated BacktestRequest for {currency_pair}, window: {window_minutes} mins ({window_size_candles} candles)"
                )
            else:
                logging.debug(
                    f"Not enough candles for {currency_pair} for window {window_minutes} mins ({window_size_candles} candles). Have {len(current_deque)}."
                )

        if generated_requests:
            logging.info(
                f"Generated {len(generated_requests)} BacktestRequests for {currency_pair} from new candle."
            )
        return generated_requests
