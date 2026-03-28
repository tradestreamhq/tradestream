# Market MCP Server

MCP server for market data. Connects to InfluxDB for candle/OHLCV data and Redis for active cryptocurrency symbols.

## Tools

| Tool | Description |
|------|-------------|
| `get_candles` | Query OHLCV candle data for a symbol. Params: `symbol`, `timeframe` (1m/5m/15m/1h/4h/1d), `start?`, `end?`, `limit` (default 100). |
| `get_latest_price` | Get most recent candle close price for a symbol. Returns price, volume_24h, change_24h. |
| `get_volatility` | Compute volatility metrics (stddev of returns, ATR) for a symbol over `period_minutes` (default 60). |
| `get_symbols` | Get active cryptocurrency symbol list from Redis (`top_cryptocurrencies` key). |
| `get_market_summary` | Aggregated summary: price, change_1h, change_24h, volume_24h, volatility, high_24h, low_24h, vwap. |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `INFLUXDB_URL` | Yes | InfluxDB server URL (e.g., `http://localhost:8086`) |
| `INFLUXDB_TOKEN` | Yes | InfluxDB authentication token |
| `INFLUXDB_ORG` | Yes | InfluxDB organization |
| `INFLUXDB_BUCKET` | Yes | InfluxDB bucket name |
| `REDIS_URL` | No | Redis URL (default: `localhost:6379`) |

### Flags

```bash
--influxdb_url       InfluxDB URL (default: http://localhost:8086)
--influxdb_token     InfluxDB authentication token
--influxdb_org       InfluxDB organization
--influxdb_bucket    InfluxDB bucket name
--redis_host         Redis host (default: localhost)
--redis_port         Redis port (default: 6379)
--mcp_transport      Transport type: stdio or sse (default: stdio)
--mcp_port           SSE server port (default: 8080)
```

## Running

### With Bazel

```bash
bazel run //services/market_mcp:app -- \
  --influxdb_token=$INFLUXDB_TOKEN \
  --influxdb_org=$INFLUXDB_ORG \
  --influxdb_bucket=$INFLUXDB_BUCKET
```

### With Docker

```bash
docker build -t market-mcp services/market_mcp/
docker run -e INFLUXDB_TOKEN=$INFLUXDB_TOKEN \
           -e INFLUXDB_ORG=$INFLUXDB_ORG \
           -e INFLUXDB_BUCKET=$INFLUXDB_BUCKET \
           market-mcp
```

## Testing

```bash
bazel test //services/market_mcp:server_test
bazel test //services/market_mcp:influxdb_client_test
bazel test //services/market_mcp:redis_client_test
```

## Architecture

- **InfluxDB**: Stores time-series candle data (measurement: `candles`, tag: `currency_pair`, fields: open/high/low/close/volume)
- **Redis**: Stores active symbol list under `top_cryptocurrencies` key (JSON array of tiingo-format symbols)
- **MCP Protocol**: Exposes tools via stdio or SSE transport
