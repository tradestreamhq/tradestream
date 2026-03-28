# Strategy MCP Server

MCP server for querying and managing trading strategy data from PostgreSQL.

## Tools

| Tool | Description |
|------|-------------|
| `get_top_strategies` | Top strategies by Sharpe ratio for a symbol (VALIDATED/DEPLOYED only) |
| `get_spec` | Full strategy_spec row by name |
| `get_performance` | Performance metrics (backtest/paper/live) for an implementation |
| `get_performance_batch` | Batch performance lookup for multiple implementations |
| `list_strategy_types` | Distinct strategy types with at least one validated implementation |
| `create_spec` | Insert a new strategy spec with `source=LLM_GENERATED` |
| `get_walk_forward` | Walk-forward validation results for an implementation |
| `get_strategy_signal` | Current signal from a specific strategy for a symbol |
| `get_strategy_consensus` | Aggregated consensus across all active strategies for a symbol |

## Configuration

Database credentials via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | — | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | — | Database password |

## Development

```bash
# Run with Bazel
bazel run //services/strategy_mcp:app -- --postgres_password=secret

# Run tests
bazel test //services/strategy_mcp:server_test //services/strategy_mcp:postgres_client_test

# Or with pytest directly
python -m pytest services/strategy_mcp/server_test.py services/strategy_mcp/postgres_client_test.py -v
```

## Docker

```bash
docker build -t strategy-mcp services/strategy_mcp/
docker run -e DB_HOST=db -e DB_NAME=tradestream -e DB_PASSWORD=secret strategy-mcp
```
