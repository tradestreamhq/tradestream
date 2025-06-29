# Candle Ingestor

A robust cryptocurrency candle data ingestion service that fetches OHLCV (Open, High, Low, Close, Volume) data from multiple exchanges using CCXT and stores it in InfluxDB.

## Overview

The Candle Ingestor supports both single-exchange and multi-exchange modes with intelligent symbol validation and automatic exchange requirement detection. It performs historical backfilling and real-time catch-up to maintain complete candle datasets.

### Key Features

- **Multi-Exchange Support**: Aggregate data from multiple exchanges (Binance, Coinbase Pro, Kraken, etc.)
- **Auto-Detection**: Automatically determines minimum exchange requirements based on configuration
- **Symbol Validation**: Validates symbol availability across exchanges before processing
- **Resilient Processing**: Built-in retries, error handling, and state tracking
- **Flexible Timeframes**: Support for 1-minute to daily candles
- **Dry Run Mode**: Test configuration without writing data

## Quick Start

### Basic Single Exchange
```bash
./candle_ingestor --exchanges=binance --run_mode=wet
```

### Multi-Exchange with Auto-Detection
```bash
# Automatically requires all 3 exchanges
./candle_ingestor --exchanges=binance,coinbasepro,kraken --run_mode=wet
```

### Custom Exchange Requirements
```bash
# Allow aggregation with 2+ out of 3 exchanges
./candle_ingestor --exchanges=binance,coinbasepro,kraken --min_exchanges_required=2 --run_mode=wet
```

## Installation

### Prerequisites

- Python 3.13+
- InfluxDB 2.x
- Redis
- Access to configured exchanges

### Environment Variables

```bash
export INFLUXDB_TOKEN="your-influxdb-token"
export INFLUXDB_ORG="your-org"
export REDIS_HOST="localhost"
```

### Running with Docker

```bash
docker run tradestreamhq/candle-ingestor:latest \
  --exchanges=binance,coinbasepro \
  --influxdb_token=$INFLUXDB_TOKEN \
  --influxdb_org=$INFLUXDB_ORG \
  --redis_host=$REDIS_HOST \
  --run_mode=wet
```

## Configuration

### Exchange Configuration

| Strategy | Command | Behavior |
|----------|---------|-----------|
| **Single Exchange** | `--exchanges=binance` | Uses only Binance data |
| **Conservative Multi** | `--exchanges=binance,coinbase,kraken` | Requires all 3 exchanges (auto-detected) |
| **Flexible Multi** | `--exchanges=binance,coinbase,kraken --min_exchanges_required=2` | Aggregates with 2+ exchanges |

### Key Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--exchanges` | `binance,coinbasepro,kraken` | Comma-separated list of exchanges |
| `--min_exchanges_required` | `0` (auto) | Minimum exchanges for aggregation (0 = auto-detect) |
| `--candle_granularity_minutes` | `1` | Candle timeframe in minutes |
| `--backfill_start_date` | `1_year_ago` | Historical data start point |
| `--run_mode` | `wet` | `wet` (live) or `dry` (simulation) |

### Auto-Detection Logic

When `--min_exchanges_required=0` (default):
- **1 exchange provided** → Single exchange mode
- **N exchanges provided** → Multi-exchange mode requiring all N exchanges

This ensures data quality by default while allowing flexibility when needed.

## Usage Examples

### Development & Testing

```bash
# Test configuration
./candle_ingestor --run_mode=dry --exchanges=binance

# Limited backfill for testing
./candle_ingestor --backfill_start_date=1_day_ago --dry_run_limit=5
```

### Production Scenarios

#### High Quality (Conservative)
```bash
# Requires all 3 exchanges for maximum data quality
./candle_ingestor --exchanges=binance,coinbasepro,kraken
```

#### Balanced (Recommended)
```bash
# Allows 2+ exchanges for better coverage
./candle_ingestor --exchanges=binance,coinbasepro,kraken --min_exchanges_required=2
```

#### Maximum Coverage
```bash
# Process symbols available on any 2+ exchanges
./candle_ingestor --exchanges=binance,coinbasepro,kraken,huobi,kucoin --min_exchanges_required=2
```

### Deployment

#### Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: candle-ingestor
            image: tradestreamhq/candle-ingestor:latest
            args: ["--exchanges=binance,coinbasepro,kraken"]
            env:
            - name: INFLUXDB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: influxdb-secret
                  key: token
```

## Data Flow

1. **Symbol Retrieval**: Fetches cryptocurrency symbols from Redis
2. **Symbol Validation**: Validates symbol availability across configured exchanges
3. **Historical Backfill**: Processes historical data from `backfill_start_date`
4. **Real-time Catch-up**: Ingests recent data since last processing
5. **Data Aggregation**: Combines multi-exchange data using volume-weighted averaging
6. **Storage**: Writes processed candles to InfluxDB with state tracking

## Multi-Exchange Aggregation

When multiple exchanges are configured, the service:

1. **Fetches data** from all available exchanges
2. **Groups candles** by timestamp
3. **Applies volume-weighted averaging** for OHLC prices
4. **Sums volumes** across exchanges
5. **Tracks source exchanges** in metadata

### Example Aggregation
```bash
# Input from 3 exchanges at timestamp 1640995200000
Binance:  Close=50100, Volume=120.5
Coinbase: Close=50050, Volume=95.2  
Kraken:   Close=50075, Volume=67.8

# Output: VWAP Close=50082.14, Total Volume=283.5
```

## State Management

The service maintains processing state in InfluxDB to ensure:
- **Idempotent execution** (safe to re-run)
- **Resumable processing** after interruptions
- **Efficient catch-up** with minimal API calls

State is tracked separately for:
- Backfill operations (`{ticker}-backfill`)
- Catch-up operations (`{ticker}-catch_up`)

## Monitoring & Observability

### Log Levels
- **INFO**: Normal operations, progress updates
- **WARNING**: Recoverable issues, symbol validation failures
- **ERROR**: Serious issues requiring attention

### Key Metrics to Monitor
- Successful vs failed symbol processing
- Exchange availability and response times
- InfluxDB write success rates
- Redis connectivity status

### Example Log Output
```
INFO: Multi-exchange mode: using 3 exchanges with binance as primary
INFO: Auto-detected min_exchanges_required: 3
INFO: Symbol validation: 45/50 symbols meet minimum 3 exchange requirement
INFO: Successfully processed 1,437 candles for BTC/USD
```

## Troubleshooting

### Common Issues

#### Symbol Validation Failures
```bash
ERROR: No symbols meet the minimum exchange requirement of 3
```
**Solution**: Lower `--min_exchanges_required` or check exchange connectivity

#### Exchange API Errors
```bash
WARNING: Failed to fetch from coinbasepro: Rate limit exceeded
```
**Solution**: Increase `--api_call_delay_seconds` or check API status

#### InfluxDB Connection Issues
```bash
ERROR: Failed to connect to InfluxDB after retries
```
**Solution**: Verify `--influxdb_url`, token, and organization settings

### Debug Mode
```bash
# Enable verbose logging
./candle_ingestor --verbosity=1 --run_mode=dry
```

## Migration from Tiingo

### Before (Tiingo API)
```bash
./candle_ingestor --tiingo_api_key=$API_KEY
```

### After (CCXT Multi-Exchange)
```bash
./candle_ingestor --exchanges=binance,coinbasepro,kraken
```

The CCXT implementation provides:
- ✅ **Higher reliability** through multi-exchange redundancy
- ✅ **Better data quality** via cross-exchange validation
- ✅ **No API key costs** for most exchanges
- ✅ **Real-time processing** capabilities

## Technical Details

### Architecture
- **Language**: Python 3.13
- **Exchange Connectivity**: CCXT library
- **Database**: InfluxDB 2.x for time-series storage
- **Cache**: Redis for symbol management
- **Containerization**: OCI-compliant images

### Performance Considerations
- Implements exponential backoff for API retries
- Batches InfluxDB writes for efficiency
- Uses connection pooling for database operations
- Respects exchange rate limits automatically

### Dependencies
- `ccxt`: Cryptocurrency exchange connectivity
- `influxdb-client`: InfluxDB Python client
- `redis`: Redis connectivity
- `tenacity`: Retry mechanisms
- `absl-py`: Application framework

## Contributing

1. **Fork** the repository
2. **Create** a feature branch
3. **Add tests** for new functionality
4. **Run tests**: `bazel test //services/candle_ingestor:all`
5. **Submit** a pull request

### Development Setup
```bash
# Run tests
bazel test //services/candle_ingestor:all

# Build container
bazel run //services/candle_ingestor:push_candle_ingestor_image

# Format code
black services/candle_ingestor/
```

## License

This project is part of the TradeStream platform. See the root LICENSE file for details.

---

**Need Help?** Check the [troubleshooting section](#troubleshooting) or review the logs for specific error messages.
