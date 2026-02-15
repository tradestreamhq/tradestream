# MCP Servers Specification

## Goal

MCP (Model Context Protocol) servers that provide tools to OpenCode agents, enabling access to TradeStream's strategy database, market data, portfolio state, backtest engine, and decision history.

## MCP Servers Overview

| Server            | Purpose                   | Data Source     | Tools                                                                 |
| ----------------- | ------------------------- | --------------- | --------------------------------------------------------------------- |
| `strategy-mcp`    | Strategy data and signals | PostgreSQL      | `get_top_strategies`, `get_strategy_signal`, `get_strategy_consensus` |
| `market-data-mcp` | Candle and price data     | InfluxDB        | `get_candles`, `get_current_price`, `get_volatility`                  |
| `portfolio-mcp`   | Portfolio state           | PostgreSQL      | `get_positions`, `get_balance`, `validate_trade`                      |
| `backtest-mcp`    | Backtest execution        | gRPC Backtester | `run_backtest`, `get_historical_performance`                          |
| `decisions-mcp`   | Agent decisions history   | PostgreSQL      | `get_recent_decisions`, `save_decision`                               |
| `strategy-db-mcp` | Strategy specs management | PostgreSQL      | `get_top_specs`, `get_implementations`, `submit_new_spec`             |

## Architecture

```
+-------------------------------------------------------------+
|                      OPENCODE AGENT                         |
|                                                             |
|   Tool Call: get_top_strategies(symbol="ETH/USD", limit=5) |
+-------------------------------------------------------------+
                              |
                    stdio transport (JSON-RPC)
                              |
                              v
+-------------------------------------------------------------+
|                    MCP SERVER PROCESS                       |
|                                                             |
|   +-----------------+    +-----------------------------+   |
|   | Tool Handler    |--->| Data Source Client          |   |
|   | (JSON schema)   |    | (PostgreSQL/InfluxDB/gRPC)  |   |
|   +-----------------+    +-----------------------------+   |
|                                                             |
|   +-----------------+    +-----------------------------+   |
|   | Response Cache  |    | Error Handler               |   |
|   | (30s TTL)       |    | (structured errors)         |   |
|   +-----------------+    +-----------------------------+   |
+-------------------------------------------------------------+
```

---

## strategy-mcp

### Purpose

Provide access to strategy performance data and current signals from PostgreSQL.

### Tools

#### get_top_strategies

```json
{
  "name": "get_top_strategies",
  "description": "Fetch top N strategies for a symbol ranked by performance score",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {
        "type": "string",
        "description": "Trading pair e.g. ETH/USD"
      },
      "limit": {
        "type": "integer",
        "default": 5,
        "maximum": 100,
        "description": "Number of strategies to return per page"
      },
      "offset": {
        "type": "integer",
        "default": 0,
        "description": "Number of strategies to skip for pagination"
      },
      "metric": {
        "type": "string",
        "enum": ["sharpe", "accuracy", "return"],
        "default": "sharpe"
      },
      "force_refresh": {
        "type": "boolean",
        "default": false,
        "description": "Bypass cache and fetch fresh data"
      }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "strategy_id": { "type": "string" },
            "name": { "type": "string" },
            "score": { "type": "number" },
            "sharpe": { "type": "number" },
            "accuracy": { "type": "number" },
            "signals_count": { "type": "integer" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "SYMBOL_NOT_FOUND",
      "description": "No strategies found for the given symbol"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    },
    {
      "code": "INVALID_METRIC",
      "description": "Specified metric is not supported"
    }
  ]
}
```

#### get_strategy_signal

```json
{
  "name": "get_strategy_signal",
  "description": "Get the current signal from a specific strategy for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "strategy_id": { "type": "string", "description": "Strategy identifier" },
      "symbol": { "type": "string", "description": "Trading pair" },
      "force_refresh": {
        "type": "boolean",
        "default": false,
        "description": "Bypass cache and fetch fresh data"
      }
    },
    "required": ["strategy_id", "symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "signal": { "type": "string", "enum": ["BUY", "SELL", "HOLD"] },
      "confidence": { "type": "number" },
      "triggered_at": { "type": "string", "format": "date-time" },
      "parameters": { "type": "object" }
    }
  },
  "errors": [
    {
      "code": "STRATEGY_NOT_FOUND",
      "description": "Strategy with specified ID does not exist"
    },
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "NO_SIGNAL",
      "description": "Strategy has no current signal for this symbol"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### get_strategy_consensus

```json
{
  "name": "get_strategy_consensus",
  "description": "Get aggregated consensus across all active strategies for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string", "description": "Trading pair" },
      "force_refresh": {
        "type": "boolean",
        "default": false,
        "description": "Bypass cache and fetch fresh data"
      }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "bullish_count": { "type": "integer" },
      "bearish_count": { "type": "integer" },
      "neutral_count": { "type": "integer" },
      "consensus": {
        "type": "string",
        "enum": ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
      },
      "confidence": { "type": "number" }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "NO_ACTIVE_STRATEGIES",
      "description": "No active strategies found for this symbol"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

---

## market-data-mcp

### Purpose

Provide access to candle data, current prices, and volatility metrics from InfluxDB.

### Tools

#### get_candles

```json
{
  "name": "get_candles",
  "description": "Fetch OHLCV candle data for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "timeframe": {
        "type": "string",
        "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "default": "1h"
      },
      "limit": { "type": "integer", "default": 100, "maximum": 1000 },
      "offset": { "type": "integer", "default": 0 },
      "force_refresh": { "type": "boolean", "default": false }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "timestamp": { "type": "string" },
            "open": { "type": "number" },
            "high": { "type": "number" },
            "low": { "type": "number" },
            "close": { "type": "number" },
            "volume": { "type": "number" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "INVALID_TIMEFRAME",
      "description": "Specified timeframe is not supported"
    },
    { "code": "NO_DATA", "description": "No candle data available" },
    {
      "code": "DATABASE_ERROR",
      "description": "InfluxDB connection or query failed"
    }
  ]
}
```

#### get_current_price

```json
{
  "name": "get_current_price",
  "description": "Get the current price and recent change for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "force_refresh": { "type": "boolean", "default": false }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "price": { "type": "number" },
      "change_1h": { "type": "number" },
      "change_24h": { "type": "number" },
      "volume_24h": { "type": "number" },
      "timestamp": { "type": "string" }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "SYMBOL_NOT_FOUND",
      "description": "No price data available for the symbol"
    },
    {
      "code": "STALE_DATA",
      "description": "Price data is older than acceptable threshold"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "InfluxDB connection or query failed"
    }
  ]
}
```

#### get_volatility

```json
{
  "name": "get_volatility",
  "description": "Calculate volatility metrics for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "timeframe": {
        "type": "string",
        "enum": ["1h", "4h", "1d"],
        "default": "1h"
      },
      "force_refresh": { "type": "boolean", "default": false }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "volatility": {
        "type": "number",
        "description": "Standard deviation of returns"
      },
      "atr": { "type": "number", "description": "Average True Range" },
      "high_low_range": { "type": "number" }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "INVALID_TIMEFRAME",
      "description": "Specified timeframe is not supported"
    },
    {
      "code": "INSUFFICIENT_DATA",
      "description": "Not enough data points to calculate volatility"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "InfluxDB connection or query failed"
    }
  ]
}
```

---

## portfolio-mcp

### Purpose

Provide access to portfolio state for position sizing and risk validation.

### Tools

#### get_positions

```json
{
  "name": "get_positions",
  "description": "Get current open positions",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {
        "type": "string",
        "description": "Optional filter by symbol"
      },
      "limit": { "type": "integer", "default": 50, "maximum": 200 },
      "offset": { "type": "integer", "default": 0 }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "symbol": { "type": "string" },
            "side": { "type": "string", "enum": ["LONG", "SHORT"] },
            "size": { "type": "number" },
            "entry_price": { "type": "number" },
            "current_price": { "type": "number" },
            "unrealized_pnl": { "type": "number" },
            "opened_at": { "type": "string" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "UNAUTHORIZED",
      "description": "Not authorized to access portfolio data"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### get_balance

```json
{
  "name": "get_balance",
  "description": "Get account balance and available margin",
  "parameters": { "type": "object", "properties": {} },
  "returns": {
    "type": "object",
    "properties": {
      "total_balance": { "type": "number" },
      "available_balance": { "type": "number" },
      "margin_used": { "type": "number" },
      "unrealized_pnl": { "type": "number" }
    }
  },
  "errors": [
    {
      "code": "UNAUTHORIZED",
      "description": "Not authorized to access balance data"
    },
    { "code": "ACCOUNT_NOT_FOUND", "description": "Trading account not found" },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### validate_trade

```json
{
  "name": "validate_trade",
  "description": "Validate a proposed trade against risk rules",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "side": { "type": "string", "enum": ["BUY", "SELL"] },
      "size": { "type": "number" },
      "price": { "type": "number" }
    },
    "required": ["symbol", "side", "size"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "valid": { "type": "boolean" },
      "reason": { "type": "string" },
      "max_size": { "type": "number" },
      "risk_score": { "type": "number" }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    { "code": "INVALID_SIDE", "description": "Trade side must be BUY or SELL" },
    { "code": "INVALID_SIZE", "description": "Trade size must be positive" },
    {
      "code": "INSUFFICIENT_BALANCE",
      "description": "Account balance insufficient for trade"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

---

## backtest-mcp

### Purpose

Provide access to backtest execution and historical performance data.

### Tools

#### run_backtest

```json
{
  "name": "run_backtest",
  "description": "Run a backtest for a strategy configuration",
  "parameters": {
    "type": "object",
    "properties": {
      "strategy_id": { "type": "string" },
      "symbol": { "type": "string" },
      "start_date": { "type": "string", "format": "date" },
      "end_date": { "type": "string", "format": "date" }
    },
    "required": ["strategy_id", "symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "total_return": { "type": "number" },
      "sharpe_ratio": { "type": "number" },
      "max_drawdown": { "type": "number" },
      "win_rate": { "type": "number" },
      "trades": { "type": "integer" }
    }
  },
  "errors": [
    {
      "code": "STRATEGY_NOT_FOUND",
      "description": "Strategy with specified ID does not exist"
    },
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "INVALID_DATE_RANGE",
      "description": "Start date must be before end date"
    },
    {
      "code": "INSUFFICIENT_DATA",
      "description": "Not enough historical data for the specified range"
    },
    {
      "code": "BACKTEST_TIMEOUT",
      "description": "Backtest execution exceeded time limit"
    },
    {
      "code": "GRPC_ERROR",
      "description": "Backtester service connection failed"
    }
  ]
}
```

#### get_historical_performance

```json
{
  "name": "get_historical_performance",
  "description": "Get historical performance metrics for a strategy",
  "parameters": {
    "type": "object",
    "properties": {
      "strategy_id": { "type": "string" },
      "symbol": { "type": "string" },
      "period": {
        "type": "string",
        "enum": ["1w", "1m", "3m", "6m", "1y"],
        "default": "3m"
      },
      "force_refresh": { "type": "boolean", "default": false }
    },
    "required": ["strategy_id"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "total_signals": { "type": "integer" },
      "accuracy": { "type": "number" },
      "avg_return": { "type": "number" },
      "sharpe": { "type": "number" },
      "performance_by_month": { "type": "array" }
    }
  },
  "errors": [
    {
      "code": "STRATEGY_NOT_FOUND",
      "description": "Strategy with specified ID does not exist"
    },
    {
      "code": "INVALID_PERIOD",
      "description": "Specified period is not supported"
    },
    {
      "code": "NO_PERFORMANCE_DATA",
      "description": "No performance data available for this strategy"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

---

## decisions-mcp

### Purpose

Provide access to agent decision history for learning and auditing.

### Tools

#### get_recent_decisions

```json
{
  "name": "get_recent_decisions",
  "description": "Get recent agent decisions for a symbol",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "limit": { "type": "integer", "default": 10, "maximum": 100 },
      "offset": { "type": "integer", "default": 0 },
      "action": { "type": "string", "enum": ["BUY", "SELL", "HOLD"] },
      "force_refresh": { "type": "boolean", "default": false }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "decision_id": { "type": "string" },
            "symbol": { "type": "string" },
            "action": { "type": "string" },
            "confidence": { "type": "number" },
            "opportunity_score": { "type": "number" },
            "reasoning": { "type": "string" },
            "created_at": { "type": "string" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "INVALID_ACTION",
      "description": "Action filter must be BUY, SELL, or HOLD"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### save_decision

```json
{
  "name": "save_decision",
  "description": "Save an agent decision to the database",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "action": { "type": "string", "enum": ["BUY", "SELL", "HOLD"] },
      "confidence": { "type": "number" },
      "opportunity_score": { "type": "number" },
      "reasoning": { "type": "string" },
      "tool_calls": { "type": "array" }
    },
    "required": ["symbol", "action", "confidence", "reasoning"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "decision_id": { "type": "string" },
      "saved": { "type": "boolean" }
    }
  },
  "errors": [
    {
      "code": "INVALID_SYMBOL",
      "description": "Symbol format is invalid or not supported"
    },
    {
      "code": "INVALID_ACTION",
      "description": "Action must be BUY, SELL, or HOLD"
    },
    {
      "code": "INVALID_CONFIDENCE",
      "description": "Confidence must be between 0 and 1"
    },
    {
      "code": "REASONING_TOO_LONG",
      "description": "Reasoning exceeds maximum length"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

---

## strategy-db-mcp

### Purpose

Provide access to strategy specs and implementations for the Learning Agent.

### Tools

#### get_top_specs

```json
{
  "name": "get_top_specs",
  "description": "Get top performing strategy specs",
  "parameters": {
    "type": "object",
    "properties": {
      "limit": { "type": "integer", "default": 10, "maximum": 100 },
      "offset": { "type": "integer", "default": 0 },
      "source": {
        "type": "string",
        "enum": ["CANONICAL", "LLM_GENERATED", "ALL"],
        "default": "ALL"
      },
      "force_refresh": { "type": "boolean", "default": false }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "spec_id": { "type": "string" },
            "name": { "type": "string" },
            "indicators": { "type": "array" },
            "avg_sharpe": { "type": "number" },
            "implementations_count": { "type": "integer" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "INVALID_SOURCE",
      "description": "Source filter must be CANONICAL, LLM_GENERATED, or ALL"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### get_implementations

```json
{
  "name": "get_implementations",
  "description": "Get implementations for a strategy spec",
  "parameters": {
    "type": "object",
    "properties": {
      "spec_id": { "type": "string" },
      "status": {
        "type": "string",
        "enum": ["CANDIDATE", "VALIDATED", "DEPLOYED", "RETIRED", "ALL"],
        "default": "VALIDATED"
      },
      "limit": { "type": "integer", "default": 10, "maximum": 100 },
      "offset": { "type": "integer", "default": 0 },
      "force_refresh": { "type": "boolean", "default": false }
    },
    "required": ["spec_id"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "impl_id": { "type": "string" },
            "parameters": { "type": "object" },
            "symbol": { "type": "string" },
            "forward_sharpe": { "type": "number" },
            "forward_accuracy": { "type": "number" },
            "status": { "type": "string" }
          }
        }
      },
      "pagination": {
        "type": "object",
        "properties": {
          "offset": { "type": "integer" },
          "limit": { "type": "integer" },
          "total": { "type": "integer" },
          "has_more": { "type": "boolean" }
        }
      }
    }
  },
  "errors": [
    {
      "code": "SPEC_NOT_FOUND",
      "description": "Strategy spec with specified ID does not exist"
    },
    { "code": "INVALID_STATUS", "description": "Status filter is not valid" },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

#### submit_new_spec

```json
{
  "name": "submit_new_spec",
  "description": "Submit a new strategy spec generated by the Learning Agent",
  "parameters": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "description": { "type": "string" },
      "indicators": { "type": "array" },
      "entry_conditions": { "type": "array" },
      "exit_conditions": { "type": "array" },
      "parameters": { "type": "array" },
      "reasoning": { "type": "string" }
    },
    "required": [
      "name",
      "indicators",
      "entry_conditions",
      "exit_conditions",
      "parameters"
    ]
  },
  "returns": {
    "type": "object",
    "properties": {
      "spec_id": { "type": "string" },
      "created": { "type": "boolean" },
      "validation_errors": { "type": "array" }
    }
  },
  "errors": [
    {
      "code": "INVALID_NAME",
      "description": "Spec name is missing or invalid"
    },
    {
      "code": "DUPLICATE_NAME",
      "description": "A spec with this name already exists"
    },
    {
      "code": "INVALID_INDICATORS",
      "description": "One or more indicators are not recognized"
    },
    {
      "code": "INVALID_CONDITIONS",
      "description": "Entry or exit conditions are malformed"
    },
    {
      "code": "SCHEMA_VALIDATION_ERROR",
      "description": "Spec does not conform to required schema"
    },
    {
      "code": "DATABASE_ERROR",
      "description": "Database connection or query failed"
    }
  ]
}
```

---

## Common Patterns

### Pagination

All list operations support pagination via `offset` and `limit` parameters. Responses include a `pagination` object:

```json
{
  "items": [...],
  "pagination": {
    "offset": 0,
    "limit": 10,
    "total": 156,
    "has_more": true
  }
}
```

**Pagination Guidelines:**

- Default `limit` varies by endpoint (typically 10-50)
- Maximum `limit` is capped per endpoint to prevent memory issues
- Use `has_more` to determine if additional pages exist
- Total count is always returned for client-side pagination UI

### Cache Invalidation

Cached endpoints support a `force_refresh` boolean parameter:

- When `false` (default): Returns cached data if available and not expired
- When `true`: Bypasses cache and fetches fresh data from the source

### Response Metadata

All tool responses include metadata:

```json
{
  "data": { ... },
  "_metadata": {
    "latency_ms": 45,
    "cached": false,
    "cache_ttl_remaining": null,
    "source": "postgresql"
  }
}
```

### Error Response

All errors follow a standardized format:

```json
{
  "error": {
    "code": "STRATEGY_NOT_FOUND",
    "message": "Strategy with ID 'abc123' not found",
    "details": {
      "strategy_id": "abc123"
    }
  },
  "_metadata": {
    "latency_ms": 12
  }
}
```

**Standard Error Codes (all servers):**
| Code | HTTP Equivalent | Description |
|------|-----------------|-------------|
| `DATABASE_ERROR` | 500 | Database connection or query failed |
| `GRPC_ERROR` | 502 | gRPC service connection failed |
| `TIMEOUT` | 504 | Operation exceeded time limit |
| `INVALID_PARAMETER` | 400 | Generic parameter validation error |
| `NOT_FOUND` | 404 | Requested resource does not exist |
| `UNAUTHORIZED` | 401 | Not authorized to access resource |

### Caching

| Tool                         | Cache TTL | Notes                                    |
| ---------------------------- | --------- | ---------------------------------------- |
| `get_top_strategies`         | 30s       | Rankings change infrequently             |
| `get_strategy_signal`        | 10s       | Signals may update frequently            |
| `get_strategy_consensus`     | 30s       | Aggregated from multiple strategies      |
| `get_current_price`          | 5s        | Near real-time price data                |
| `get_candles`                | 60s       | Historical data, stable                  |
| `get_volatility`             | 30s       | Computed metric                          |
| `get_balance`                | None      | Always fresh for trading decisions       |
| `get_positions`              | None      | Always fresh for trading decisions       |
| `get_recent_decisions`       | 30s       | Historical decisions                     |
| `get_top_specs`              | 60s       | Spec rankings                            |
| `get_implementations`        | 30s       | Implementation data                      |
| `get_historical_performance` | 5m        | Historical metrics, expensive to compute |

### Connection Pooling

Each MCP server maintains connection pools for its data sources:

**PostgreSQL Connection Pool:**

```
min_connections: 2
max_connections: 10
idle_timeout: 300s
connection_timeout: 5s
```

**InfluxDB Connection Pool:**

```
max_connections: 5
idle_timeout: 60s
connection_timeout: 3s
```

**gRPC Connection Pool (Backtester):**

```
max_connections: 3
keepalive_interval: 30s
keepalive_timeout: 10s
```

## Constraints

- Each MCP server runs as a separate process
- Servers implement stdio transport (JSON-RPC over stdin/stdout)
- Tool responses include latency metadata
- Failed tool calls return structured errors with specific error codes
- Results cached where appropriate (configurable TTL)
- All list operations support pagination to prevent memory issues
- Connection pooling for database connections with configurable limits

## Acceptance Criteria

- [ ] Each MCP server implements stdio transport
- [ ] All tools have JSON schema definitions
- [ ] Tools callable from OpenCode via config
- [ ] Error handling returns structured errors with documented codes
- [ ] Response metadata includes latency
- [ ] Caching works with configurable TTL and force_refresh bypass
- [ ] All list operations support pagination
- [ ] Connection pooling configured for all data sources
- [ ] Unit tests for each tool
- [ ] Integration tests with real databases

## File Structure

```
services/mcp_servers/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── server.py          # Base MCP server class
│   ├── cache.py           # Caching utilities with force_refresh support
│   ├── errors.py          # Structured error types and codes
│   ├── pagination.py      # Pagination helpers
│   └── pool.py            # Connection pool management
├── strategy_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── market_data_mcp/
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── portfolio_mcp/
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── backtest_mcp/
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── decisions_mcp/
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── strategy_db_mcp/
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── requirements.txt
└── Dockerfile
```
