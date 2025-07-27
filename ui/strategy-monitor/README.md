# Strategy Monitor UI

A real-time visualization dashboard for monitoring trading strategies in the TradeStream system.

## Features

- **Strategy Cloud Visualization**: Interactive bubble chart showing strategy types sized by frequency and colored by performance
- **Snowflake Grid View**: Clean grid layout showing top-performing strategies
- **Real-time Metrics**: Live strategy counts, performance statistics, and system health
- **API Integration**: Connects to live PostgreSQL database through REST API
- **Auto-refresh**: Configurable automatic data updates

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend UI   │    │   Strategy API   │    │   PostgreSQL    │
│   (port 3000)   │◄──►│   (port 8080)    │◄──►│   (port 5432)   │
│                 │    │                  │    │                 │
│ • D3.js visuals │    │ • Flask REST API │    │ • Strategies    │
│ • Responsive UI │    │ • Real-time data │    │ • Metrics data  │
│ • Auto-refresh  │    │ • CORS enabled   │    │ • Live updates  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+ with pip
- Kubernetes cluster with TradeStream deployed
- kubectl configured for cluster access

### Setup

1. **Start port forwards to access services:**

   ```bash
   kubectl port-forward -n tradestream-dev svc/tradestream-dev-postgresql 5432:5432 &
   ```

2. **Install Python dependencies:**

   ```bash
   pip3 install psycopg2-binary flask flask-cors
   ```

3. **Get database password:**

   ```bash
   DB_PASSWORD=$(kubectl get secret -n tradestream-dev tradestream-dev-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d)
   ```

4. **Start the API server:**

   ```bash
   cd services/strategy_monitor_api
   python3 main.py --postgres_password=$DB_PASSWORD --api_port=8080 &
   ```

5. **Start the UI server:**

   ```bash
   cd ui/strategy-monitor
   python3 -m http.server 3000 &
   ```

6. **Open the dashboard:**
   ```
   http://localhost:3000
   ```

## API Endpoints

### Health Check

- `GET /api/health` - Service health status

### Strategies

- `GET /api/strategies` - Get all strategies (with optional filters)
- `GET /api/strategies?limit=10` - Limit results
- `GET /api/strategies?symbol=BTC/USD` - Filter by symbol
- `GET /api/strategies?strategy_type=SMA_RSI` - Filter by type
- `GET /api/strategies?min_score=0.8` - Filter by minimum score
- `GET /api/strategies/{id}` - Get specific strategy

### Metadata

- `GET /api/metrics` - Aggregated system metrics
- `GET /api/symbols` - List all trading symbols
- `GET /api/strategy-types` - List all strategy types

## Development

### Running in Development Mode

```bash
# API with debug logging
python3 main.py --postgres_password=$DB_PASSWORD --api_port=8080 --api_host=0.0.0.0

# UI with live reload (optional - use any HTTP server)
python3 -m http.server 3000
```

### Customizing Visualizations

The UI uses D3.js for visualizations. Key functions to modify:

- `renderStrategyCloud()` - Bubble chart visualization
- `renderSnowflakeGrid()` - Grid layout for strategies
- `renderTopStrategies()` - Performance rankings
- `renderMetrics()` - System statistics

### Adding New Metrics

1. Add database query in `fetch_strategy_metrics_async()`
2. Update `/api/metrics` endpoint response
3. Modify `renderMetrics()` in the UI to display new data

## Data Schema

### Strategy Object

```json
{
  "strategy_id": "uuid",
  "symbol": "BTC/USD",
  "strategy_type": "SMA_RSI",
  "parameters": {...},
  "current_score": 0.95,
  "strategy_hash": "...",
  "discovery_symbol": "BTC/USD",
  "discovery_start_time": "2025-07-01T18:56:00",
  "discovery_end_time": "2025-07-02T21:33:00",
  "first_discovered_at": "2025-07-03T04:55:47.774451",
  "last_evaluated_at": "2025-07-03T04:55:47.774451",
  "created_at": "2025-07-03T04:55:47.774451",
  "updated_at": "2025-07-03T04:55:47.774451"
}
```

### Metrics Object

```json
{
  "total_strategies": 5051,
  "total_symbols": 1,
  "total_strategy_types": 8,
  "avg_score": 0.716,
  "max_score": 0.992,
  "min_score": 0.312,
  "recent_strategies_24h": 0,
  "top_strategy_types": [...],
  "top_symbols": [...]
}
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure PostgreSQL port-forward is active
   - Verify database password is correct
   - Check that PostgreSQL pod is running

2. **API Returns Empty Data**
   - Confirm strategies exist in database: `SELECT COUNT(*) FROM strategies;`
   - Check API logs for errors
   - Verify table schema matches expected format

3. **CORS Errors in UI**
   - API includes CORS headers, but check browser dev tools
   - Ensure API is running on correct port (8080)
   - Try accessing API directly: `curl http://localhost:8080/api/health`

4. **UI Shows Mock Data**
   - Check browser dev tools console for API connection errors
   - Verify API is accessible from browser
   - Confirm no firewall blocking localhost requests

### Database Queries

Useful queries for debugging:

```sql
-- Check strategy counts by type
SELECT strategy_type, COUNT(*) FROM strategies WHERE is_active = TRUE GROUP BY strategy_type;

-- View recent strategies
SELECT * FROM strategies WHERE created_at > NOW() - INTERVAL '1 day' ORDER BY created_at DESC LIMIT 10;

-- Check score distribution
SELECT
  MIN(current_score) as min_score,
  AVG(current_score) as avg_score,
  MAX(current_score) as max_score
FROM strategies WHERE is_active = TRUE;
```

## Production Deployment

For production deployment, consider:

1. **Security**: Add authentication, HTTPS, input validation
2. **Performance**: Database connection pooling, caching, pagination
3. **Monitoring**: Application metrics, error tracking, health checks
4. **Scaling**: Load balancing, horizontal scaling, CDN for static assets

## License

Part of the TradeStream project.
