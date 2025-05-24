"""Test utilities for backtest_request_factory tests."""

from datetime import datetime, timezone
from protos.marketdata_pb2 import Candle
from protos.backtesting_pb2 import BacktestRequest
from protos.strategies_pb2 import Strategy, StrategyType
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf import any_pb2


def create_test_candle(
    currency_pair: str = "BTC/USD",
    timestamp_ms: int = None,
    open_price: float = 50000.0,
    high_price: float = 51000.0,
    low_price: float = 49000.0,
    close_price: float = 50500.0,
    volume: float = 1000.0,
) -> Candle:
    """Create a test candle with given parameters."""
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


def create_test_candles(
    count: int,
    currency_pair: str = "BTC/USD",
    start_timestamp_ms: int = None,
    interval_ms: int = 60000,  # 1 minute
) -> list[Candle]:
    """Create a list of test candles with sequential timestamps."""
    if start_timestamp_ms is None:
        start_timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    candles = []
    for i in range(count):
        timestamp_ms = start_timestamp_ms + (i * interval_ms)
        price_base = 50000.0 + (i * 10)  # Gradually increase price
        candle = create_test_candle(
            currency_pair=currency_pair,
            timestamp_ms=timestamp_ms,
            open_price=price_base,
            high_price=price_base + 100,
            low_price=price_base - 100,
            close_price=price_base + 50,
            volume=1000.0 + i,
        )
        candles.append(candle)

    return candles


def create_test_strategy(
    strategy_type: StrategyType = StrategyType.SMA_RSI, parameters: any_pb2.Any = None
) -> Strategy:
    """Create a test strategy with given parameters."""
    if parameters is None:
        parameters = any_pb2.Any()

    return Strategy(type=strategy_type, parameters=parameters)


def create_test_backtest_request(
    candles: list[Candle] = None, strategy: Strategy = None
) -> BacktestRequest:
    """Create a test backtest request."""
    if candles is None:
        candles = [create_test_candle()]
    if strategy is None:
        strategy = create_test_strategy()

    return BacktestRequest(candles=candles, strategy=strategy)


class MockInfluxRecord:
    """Mock InfluxDB record for testing."""

    def __init__(self, timestamp: datetime, values: dict):
        self._time = timestamp
        self.values = values

    def get_time(self):
        return self._time


class MockInfluxTable:
    """Mock InfluxDB table for testing."""

    def __init__(self, records: list[MockInfluxRecord]):
        self.records = records


def create_mock_influx_response(candles_data: list[dict]) -> list[MockInfluxTable]:
    """Create mock InfluxDB response from candle data."""
    records = []
    for data in candles_data:
        timestamp = datetime.fromtimestamp(data["timestamp_ms"] / 1000, tz=timezone.utc)
        values = {
            "currency_pair": data.get("currency_pair", "BTC/USD"),
            "open": data.get("open", 50000.0),
            "high": data.get("high", 51000.0),
            "low": data.get("low", 49000.0),
            "close": data.get("close", 50500.0),
            "volume": data.get("volume", 1000.0),
        }
        records.append(MockInfluxRecord(timestamp, values))

    return [MockInfluxTable(records)] if records else []


def assert_candles_equal(candle1: Candle, candle2: Candle) -> None:
    """Assert that two candles are equal."""
    assert candle1.currency_pair == candle2.currency_pair
    assert candle1.timestamp.seconds == candle2.timestamp.seconds
    assert candle1.timestamp.nanos == candle2.timestamp.nanos
    assert abs(candle1.open - candle2.open) < 0.01
    assert abs(candle1.high - candle2.high) < 0.01
    assert abs(candle1.low - candle2.low) < 0.01
    assert abs(candle1.close - candle2.close) < 0.01
    assert abs(candle1.volume - candle2.volume) < 0.01


def get_candle_timestamp_ms(candle: Candle) -> int:
    """Get timestamp in milliseconds from a candle."""
    return candle.timestamp.seconds * 1000 + candle.timestamp.nanos // 1_000_000
