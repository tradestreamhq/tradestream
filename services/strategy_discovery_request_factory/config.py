"""Configuration constants for Strategy Discovery Request Factory (Cron Job Version)."""

# Fibonacci sequence windows in minutes for strategy discovery
# These represent different time horizons for backtesting
FIBONACCI_WINDOWS_MINUTES = [5, 8, 13, 21, 34, 55, 89, 144]

# Maximum length of candle deques to prevent memory issues
DEQUE_MAXLEN = 1000

# Default parameters for strategy discovery
DEFAULT_TOP_N = 5  # Number of top strategies to discover
DEFAULT_MAX_GENERATIONS = 30  # GA maximum generations
DEFAULT_POPULATION_SIZE = 50  # GA population size

# Candle granularity in minutes (assuming 1-minute candles)
CANDLE_GRANULARITY_MINUTES = 1

# Redis configuration defaults
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_CRYPTO_SYMBOLS_KEY = "crypto:symbols"

# InfluxDB configuration defaults
DEFAULT_INFLUXDB_URL = "http://localhost:8086"
DEFAULT_INFLUXDB_BUCKET = "marketdata"

# Kafka configuration defaults
DEFAULT_KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_KAFKA_TOPIC = "strategy-discovery-requests"

# Processing defaults
DEFAULT_LOOKBACK_MINUTES = 60  # How far back to look for candles on first run

# Persistence defaults
DEFAULT_TRACKER_FILE_PATH = "/tmp/strategy_discovery_last_processed.json"
