# MCP Servers Specification

## Goal

MCP (Model Context Protocol) servers that provide tools to OpenCode agents, enabling access to TradeStream's strategy database, market data, portfolio state, backtest engine, and decision history.

## MCP Servers Overview

| Server | Purpose | Data Source | Tools |
|--------|---------|-------------|-------|
| `strategy-mcp` | Strategy data and signals | PostgreSQL | `get_top_strategies`, `get_strategy_signal`, `get_strategy_consensus` |
| `market-data-mcp` | Candle and price data | InfluxDB | `get_candles`, `get_current_price`, `get_volatility` |
| `portfolio-mcp` | Portfolio state | PostgreSQL | `get_positions`, `get_balance`, `validate_trade` |
| `backtest-mcp` | Backtest execution | gRPC Backtester | `run_backtest`, `get_historical_performance` |
| `decisions-mcp` | Agent decisions history | PostgreSQL | `get_recent_decisions`, `save_decision` |
| `strategy-db-mcp` | Strategy specs management | PostgreSQL | `get_top_specs`, `get_implementations`, `submit_new_spec` |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OPENCODE AGENT                         │
│                                                             │
│   Tool Call: get_top_strategies(symbol="ETH/USD", limit=5) │
└─────────────────────────────────────────────────────────────┘
                              │
                    stdio transport (JSON-RPC)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP SERVER PROCESS                       │
│                                                             │
│   ┌─────────────────┐    ┌─────────────────────────────┐   │
│   │ Tool Handler    │───▶│ Data Source Client          │   │
│   │ (JSON schema)   │    │ (PostgreSQL/InfluxDB/gRPC)  │   │
│   └─────────────────┘    └─────────────────────────────┘   │
│                                                             │
│   ┌─────────────────┐    ┌─────────────────────────────┐   │
│   │ Response Cache  │    │ Error Handler               │   │
│   │ (30s TTL)       │    │ (structured errors)         │   │
│   └─────────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
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
        "description": "Number of strategies to return"
      },
      "metric": {
        "type": "string",
        "enum": ["sharpe", "accuracy", "return"],
        "default": "sharpe",
        "description": "Ranking metric"
      }
    },
    "required": ["symbol"]
  },
  "returns": {
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
  }
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
      "strategy_id": {
        "type": "string",
        "description": "Strategy identifier"
      },
      "symbol": {
        "type": "string",
        "description": "Trading pair"
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
  }
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
      "symbol": {
        "type": "string",
        "description": "Trading pair"
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
      "consensus": { "type": "string", "enum": ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"] },
      "confidence": { "type": "number" }
    }
  }
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
      "limit": {
        "type": "integer",
        "default": 100,
        "maximum": 1000
      }
    },
    "required": ["symbol"]
  },
  "returns": {
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
  }
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
      "symbol": { "type": "string" }
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
  }
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
      }
    },
    "required": ["symbol"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "volatility": { "type": "number", "description": "Standard deviation of returns" },
      "atr": { "type": "number", "description": "Average True Range" },
      "high_low_range": { "type": "number" }
    }
  }
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
      }
    }
  },
  "returns": {
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
  }
}
```

#### get_balance

```json
{
  "name": "get_balance",
  "description": "Get account balance and available margin",
  "parameters": {
    "type": "object",
    "properties": {}
  },
  "returns": {
    "type": "object",
    "properties": {
      "total_balance": { "type": "number" },
      "available_balance": { "type": "number" },
      "margin_used": { "type": "number" },
      "unrealized_pnl": { "type": "number" }
    }
  }
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
  }
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
  }
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
      }
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
  }
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
      "limit": { "type": "integer", "default": 10 },
      "action": {
        "type": "string",
        "enum": ["BUY", "SELL", "HOLD"]
      }
    }
  },
  "returns": {
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
  }
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
  }
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
      "limit": { "type": "integer", "default": 10 },
      "source": {
        "type": "string",
        "enum": ["CANONICAL", "LLM_GENERATED", "ALL"],
        "default": "ALL"
      }
    }
  },
  "returns": {
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
  }
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
      "limit": { "type": "integer", "default": 10 }
    },
    "required": ["spec_id"]
  },
  "returns": {
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
  }
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
    "required": ["name", "indicators", "entry_conditions", "exit_conditions", "parameters"]
  },
  "returns": {
    "type": "object",
    "properties": {
      "spec_id": { "type": "string" },
      "created": { "type": "boolean" },
      "validation_errors": { "type": "array" }
    }
  }
}
```

---

## Common Patterns

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

### Caching

- `get_top_strategies`: 30 second cache
- `get_current_price`: 5 second cache
- `get_candles`: 60 second cache
- `get_balance`: No cache
- `get_positions`: No cache

## Constraints

- Each MCP server runs as a separate process
- Servers implement stdio transport (JSON-RPC over stdin/stdout)
- Tool responses include latency metadata
- Failed tool calls return structured errors
- Results cached where appropriate (configurable TTL)
- Connection pooling for database connections

## Acceptance Criteria

- [ ] Each MCP server implements stdio transport
- [ ] All tools have JSON schema definitions
- [ ] Tools callable from OpenCode via config
- [ ] Error handling returns structured errors
- [ ] Response metadata includes latency
- [ ] Caching works with configurable TTL
- [ ] Unit tests for each tool
- [ ] Integration tests with real databases

## File Structure

```
services/mcp_servers/
├── __init__.py
├── common/
│   ├── __init__.py
│   ├── server.py          # Base MCP server class
│   ├── cache.py           # Caching utilities
│   └── errors.py          # Structured error types
├── strategy_mcp/
│   ├── __init__.py
│   ├── server.py          # Strategy MCP server
│   ├── tools.py           # Tool implementations
│   └── tests/
│       └── test_strategy_tools.py
├── market_data_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── portfolio_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── backtest_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── decisions_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── strategy_db_mcp/
│   ├── __init__.py
│   ├── server.py
│   ├── tools.py
│   └── tests/
├── requirements.txt
└── Dockerfile
```
