"""Test utilities for strategy_discovery_request_factory tests."""

from datetime import datetime, timezone
from protos.marketdata_pb2 import Candle
from protos.discovery_pb2 import StrategyDiscoveryRequest, GAConfig
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp


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


def create_test_ga_config(
    max_generations: int = 30, population_size: int = 50
) -> GAConfig:
    """Create a test GA configuration."""
    return GAConfig(max_generations=max_generations, population_size=population_size)


def create_test_strategy_discovery_request(
    symbol: str = "BTC/USD",
    start_timestamp_ms: int = None,
    end_timestamp_ms: int = None,
    strategy_type: StrategyType = StrategyType.SMA_RSI,
    top_n: int = 5,
    ga_config: GAConfig = None,
) -> StrategyDiscoveryRequest:
    """Create a test strategy discovery request."""
    if start_timestamp_ms is None:
        start_timestamp_ms = (
            int(datetime.now(timezone.utc).timestamp() * 1000) - 300000
        )  # 5 mins ago
    if end_timestamp_ms is None:
        end_timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if ga_config is None:
        ga_config = create_test_ga_config()

    start_time = Timestamp()
    start_time.FromMilliseconds(start_timestamp_ms)

    end_time = Timestamp()
    end_time.FromMilliseconds(end_timestamp_ms)

    return StrategyDiscoveryRequest(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        strategy_type=strategy_type,
        top_n=top_n,
        ga_config=ga_config,
    )


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


def assert_strategy_discovery_requests_equal(
    req1: StrategyDiscoveryRequest, req2: StrategyDiscoveryRequest
) -> None:
    """Assert that two strategy discovery requests are equal."""
    assert req1.symbol == req2.symbol
    assert req1.start_time.seconds == req2.start_time.seconds
    assert req1.start_time.nanos == req2.start_time.nanos
    assert req1.end_time.seconds == req2.end_time.seconds
    assert req1.end_time.nanos == req2.end_time.nanos
    assert req1.strategy_type == req2.strategy_type
    assert req1.top_n == req2.top_n
    assert req1.ga_config.max_generations == req2.ga_config.max_generations
    assert req1.ga_config.population_size == req2.ga_config.population_size


def get_strategy_discovery_request_time_range_ms(
    req: StrategyDiscoveryRequest,
) -> tuple[int, int]:
    """Get start and end timestamps in milliseconds from a strategy discovery request."""
    start_ms = req.start_time.seconds * 1000 + req.start_time.nanos // 1_000_000
    end_ms = req.end_time.seconds * 1000 + req.end_time.nanos // 1_000_000
    return start_ms, end_ms
