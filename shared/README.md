# Shared Libraries

This directory contains shared utilities and libraries used across multiple services in the TradeStream platform. These components provide common functionality that can be reused by different services.

## Production System Overview

The shared libraries support the production platform:

- **Status**: ✅ **PRODUCTION** - All shared libraries operational
- **Integration**: Used by data ingestion and portfolio management services
- **APIs**: CoinMarketCap API integration for cryptocurrency data
- **Databases**: InfluxDB and PostgreSQL persistence utilities
- **Reliability**: Robust error handling and retry mechanisms

## Overview

The shared libraries are designed to be:
- **Language-agnostic**: Available for both Java/Kotlin and Python services
- **Well-tested**: Comprehensive test coverage for reliability
- **Documented**: Clear APIs and usage examples
- **Versioned**: Proper dependency management through Bazel

## Directory Structure

```
shared/
├── cryptoclient/     # Cryptocurrency API clients and utilities
└── persistence/      # Database persistence utilities
```

## Components

### Cryptoclient (✅ Production)

The `cryptoclient` module provides utilities for interacting with cryptocurrency APIs and data sources.

#### Features
- **CoinMarketCap Integration**: Client for CoinMarketCap API
- **Symbol Management**: Utilities for handling cryptocurrency symbols
- **Rate Limiting**: Built-in rate limiting for API calls
- **Error Handling**: Robust error handling and retry logic

#### Production Usage

The cryptoclient is used by the `top_crypto_updater` service to maintain the list of actively traded cryptocurrency symbols:

```python
from shared.cryptoclient.cmc_client import CMCClient

# Initialize client
client = CMCClient(api_key="your-api-key")

# Get top cryptocurrencies
top_crypto = client.get_top_cryptocurrencies(limit=100)
```

**Production Integration**:
- **Service**: `top_crypto_updater` (CronJob */15 minutes)
- **API**: CoinMarketCap API for real-time rankings
- **Output**: Redis key `top_cryptocurrencies` for symbol management
- **Scale**: 20 symbols updated per execution from CMC API rankings

#### Testing
```bash
bazel test //shared/cryptoclient:all
```

### Persistence (✅ Production)

The `persistence` module provides utilities for database operations and state management.

#### Features
- **InfluxDB Integration**: Time-series data persistence utilities
- **State Tracking**: Last processed timestamp tracking
- **Bulk Operations**: Efficient bulk data operations
- **Connection Management**: Connection pooling and lifecycle management

#### Production Usage

The persistence module is used by the `candle_ingestor` service for state tracking and data persistence:

```python
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker

# Initialize tracker
tracker = InfluxDBLastProcessedTracker(
    client=influxdb_client,
    bucket="trading_data",
    measurement="candles"
)

# Get last processed timestamp
last_processed = tracker.get_last_processed_timestamp("BTC/USD")

# Update last processed timestamp
tracker.update_last_processed_timestamp("BTC/USD", timestamp)
```

**Production Integration**:
- **Service**: `candle_ingestor` (CronJob */1 minute)
- **Database**: InfluxDB time-series database
- **Scale**: 1000+ candle writes per minute, 365-day retention
- **State**: Automatic catch-up processing for missed data

#### Testing
```bash
bazel test //shared/persistence:all
```

## Development

### Building Shared Libraries
```bash
# Build all shared libraries
bazel build //shared/...

# Build specific library
bazel build //shared/cryptoclient:all
```

### Running Tests
```bash
# Test all shared libraries
bazel test //shared/...

# Test specific library
bazel test //shared/cryptoclient:all
```

## Integration

### Java/Kotlin Services
Shared libraries are available to Java/Kotlin services through Bazel dependencies:

```python
# In BUILD file
java_library(
    name = "my_service",
    srcs = ["MyService.java"],
    deps = [
        "//shared/cryptoclient:cmc_client",
        "//shared/persistence:influxdb_tracker",
    ],
)
```

### Python Services
Python services can import shared libraries directly:

```python
from shared.cryptoclient.cmc_client import CMCClient
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker
```

## Production Performance Metrics

**Shared Libraries System** (Verified Production Metrics):
- **API Integration**: CoinMarketCap API integration for cryptocurrency data
- **Database Performance**: Efficient InfluxDB and PostgreSQL operations
- **State Management**: Reliable state tracking for data processing
- **Error Handling**: Robust retry mechanisms and error recovery
- **Scalability**: Support for high-volume data processing

**Infrastructure Performance** (Production Verified):
- **InfluxDB Integration**: 1000+ candle writes per minute with state tracking
- **API Performance**: Efficient CoinMarketCap API integration with rate limiting
- **Memory Usage**: Efficient connection pooling and resource management
- **Reliability**: Automatic error recovery and retry mechanisms

## Best Practices

### Adding New Shared Libraries

1. **Create Directory**: Add new directory under `shared/`
2. **Add BUILD File**: Include appropriate Bazel targets
3. **Write Tests**: Comprehensive test coverage
4. **Documentation**: Clear README and docstrings
5. **Versioning**: Proper dependency management

### Code Standards

- **Python**: Use black for formatting, follow PEP 8
- **Java/Kotlin**: Use google-java-format/ktlint
- **Testing**: Comprehensive unit and integration tests
- **Documentation**: Clear API documentation

### Error Handling

All shared libraries should implement:
- Graceful error handling
- Retry logic where appropriate
- Meaningful error messages
- Logging for debugging

### Performance

- Implement caching where beneficial
- Use connection pooling for database operations
- Respect rate limits for external APIs
- Optimize for common use cases

## Configuration

Shared libraries can be configured through:
- Environment variables
- Configuration files
- Dependency injection (Guice for Java/Kotlin)
- Command-line arguments

## Monitoring

Shared libraries should:
- Log important operations
- Expose metrics for monitoring
- Handle errors gracefully
- Provide health check endpoints

## Testing Strategy

### Unit Tests
- Test individual functions and classes
- Mock external dependencies
- Test error conditions
- Verify expected behavior

### Integration Tests
- Test with real external services
- Verify end-to-end functionality
- Test configuration scenarios
- Performance testing

### Test Examples

```python
def test_cmc_client_get_top_cryptocurrencies():
    client = CMCClient(api_key="test-key")
    result = client.get_top_cryptocurrencies(limit=10)
    assert len(result) == 10
    assert all(isinstance(crypto, dict) for crypto in result)
```

## Contributing

When contributing to shared libraries:

1. **Follow Patterns**: Use existing code patterns and conventions
2. **Add Tests**: Include comprehensive test coverage
3. **Update Documentation**: Keep README and docstrings current
4. **Consider Impact**: Changes affect multiple services
5. **Version Compatibility**: Maintain backward compatibility

## Dependencies

### External Dependencies
- `ccxt`: Cryptocurrency exchange connectivity
- `influxdb-client`: InfluxDB Python client
- `requests`: HTTP client library
- `tenacity`: Retry mechanisms

### Internal Dependencies
- Protocol Buffers for data contracts
- Bazel for build management
- Testing frameworks (pytest, JUnit)

## License

This project is part of the TradeStream platform. See the root LICENSE file for details. 