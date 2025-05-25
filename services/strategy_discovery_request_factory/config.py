import os
from protos.strategies_pb2 import StrategyType

# InfluxDB Configuration
INFLUXDB_URL = os.getenv(
    "INFLUXDB_URL", "http://influxdb.tradestream-namespace.svc.cluster.local:8086"
)
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET_CANDLES = os.getenv(
    "INFLUXDB_BUCKET_CANDLES", "tradestream-data"
)  # Assuming candles are in the same bucket as candle_ingestor writes

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_STRATEGY_DISCOVERY_REQUEST_TOPIC = os.getenv(
    "KAFKA_STRATEGY_DISCOVERY_REQUEST_TOPIC", "strategy-discovery-requests"
)

# Fibonacci Window Sizes (in minutes)
# Inspired by App.java: "0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025, 121393, 196418, 317811, 514229"
# Filtered for > 1440 minutes (1 day) and < 131,400 minutes (approx 3 months)
FIBONACCI_WINDOWS_MINUTES = [
    1597,  # ~1.1 days
    2584,  # ~1.8 days
    4181,  # ~2.9 days
    6765,  # ~4.7 days
    10946,  # ~7.6 days
    17711,  # ~12.3 days
    28657,  # ~19.9 days
    46368,  # ~32.2 days
    75025,  # ~52.1 days
    121393,  # ~84.3 days
]

# Deque Configuration
# Max length to accommodate the largest Fibonacci window (121393 candles if 1-minute granularity)
# Add some buffer, or ensure it's at least the max window size.
# If candle granularity is 1 minute, this is fine. If granularity changes, this needs adjustment.
DEQUE_MAXLEN = 130000  # Slightly more than max fib window

# CMC Configuration
TOP_N_CRYPTOS = int(os.getenv("TOP_N_CRYPTOS", "20"))
CMC_API_KEY = os.getenv("CMC_API_KEY")  # Essential for fetching top N cryptos

# Strategy Discovery Request Defaults
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "5"))

# GA Configuration Defaults
DEFAULT_MAX_GENERATIONS = int(os.getenv("DEFAULT_MAX_GENERATIONS", "30"))
DEFAULT_POPULATION_SIZE = int(os.getenv("DEFAULT_POPULATION_SIZE", "50"))

# Candle Granularity (used to interpret Fibonacci windows if they are in number of candles)
# Assume 1-minute candles from InfluxDB as per candle_ingestor's default.
# If Fibonacci windows are in minutes, this helps determine how many candles that is.
# For this implementation, FIBONACCI_WINDOWS_MINUTES is directly used.
CANDLE_GRANULARITY_MINUTES = int(os.getenv("CANDLE_GRANULARITY_MINUTES", "1"))
