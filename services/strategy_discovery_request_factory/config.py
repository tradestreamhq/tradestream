"""Configuration constants for Strategy Discovery Request Factory (Cron Job Version)."""

# Fibonacci sequence windows in minutes for strategy discovery
# These represent different time horizons for backtesting
FIBONACCI_WINDOWS_MINUTES = [
    5,
    8,
    13,
    21,
    34,
    55,
    89,
    144,
]  # Kept shorter for cron job efficiency

# Maximum length of candle deques to prevent memory issues
DEQUE_MAXLEN = (
    max(FIBONACCI_WINDOWS_MINUTES) + 10
)  # Ensure it's larger than the largest window

# Default parameters for strategy discovery
DEFAULT_TOP_N = 3  # Number of top strategies to discover per window/type
DEFAULT_MAX_GENERATIONS = 20  # GA maximum generations (reduced for cron)
DEFAULT_POPULATION_SIZE = 30  # GA population size (reduced for cron)

# Candle granularity in minutes (assuming 1-minute candles from InfluxDB)
CANDLE_GRANULARITY_MINUTES = 1

# Redis configuration defaults (align with flags in main.py for fetching symbols)
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB_SYMBOLS = 0  # Specific DB for symbols
DEFAULT_CRYPTO_SYMBOLS_KEY = "top_cryptocurrencies"

# InfluxDB configuration defaults (align with flags in main.py)
DEFAULT_INFLUXDB_URL = "http://localhost:8086"
DEFAULT_INFLUXDB_BUCKET_CANDLES = "tradestream-data"
DEFAULT_INFLUXDB_BUCKET_TRACKER = "tradestream-data"  # Can be the same or different
DEFAULT_INFLUXDB_TRACKER_SERVICE_NAME = "strategy_discovery"


# Kafka configuration defaults (align with flags in main.py)
DEFAULT_KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_KAFKA_TOPIC = "strategy-discovery-requests"

# Processing defaults
DEFAULT_LOOKBACK_MINUTES = (
    60 * 24 * 7
)  # How far back to look for candles on first run for a symbol (1 week)
