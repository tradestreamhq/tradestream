# Signal Generator Agent Specification

## Goal

OpenCode agent that analyzes trading symbols and generates raw BUY/SELL/HOLD signals with confidence scores and strategy breakdowns.

## Target Behavior

The Signal Generator Agent is the first stage in the signal pipeline. It runs every 1 minute for each active symbol (in parallel), uses MCP tools to gather strategy and market data, and outputs raw signals for downstream processing.

### Signal Output Format

```json
{
  "signal_id": "sig-abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "strategies_analyzed": 5,
  "strategies_bullish": 4,
  "strategies_bearish": 1,
  "strategies_neutral": 0,
  "top_strategy": {
    "name": "RSI_REVERSAL",
    "score": 0.89,
    "signal": "BUY",
    "parameters": {
      "rsiPeriod": 14,
      "oversold": 30
    }
  },
  "strategy_breakdown": [
    {"name": "RSI_REVERSAL", "signal": "BUY", "score": 0.89},
    {"name": "MACD_CROSS", "signal": "BUY", "score": 0.85},
    {"name": "BOLLINGER_BOUNCE", "signal": "BUY", "score": 0.78},
    {"name": "EMA_TREND", "signal": "BUY", "score": 0.72},
    {"name": "VOLUME_BREAKOUT", "signal": "SELL", "score": 0.65}
  ],
  "reasoning": "Strong consensus among top strategies. RSI shows oversold recovery at 28, MACD just crossed bullish with histogram expanding. 4 of 5 top strategies signal BUY.",
  "market_context": {
    "current_price": 2450.50,
    "price_change_1h": 0.023,
    "volume_ratio": 1.45,
    "volatility_1h": 0.018
  },
  "timestamp": "2025-02-01T12:34:56Z"
}
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SIGNAL GENERATOR AGENT (OpenCode)                         │
│                                                             │
│  System Prompt:                                             │
│  "You are a trading signal analyst. Analyze symbols using  │
│   available tools and generate BUY/SELL/HOLD signals."     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Servers                                          │   │
│  │  • strategy-mcp: get_top_strategies, get_signals    │   │
│  │  • market-data-mcp: get_candles, get_current_price  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  • analyze-symbol: Full symbol analysis workflow     │   │
│  │  • detect-patterns: Pattern recognition prompts      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: Raw signal → Redis channel:raw-signals            │
└─────────────────────────────────────────────────────────────┘
```

### Analysis Workflow

1. **Fetch Top Strategies**: Call `get_top_strategies(symbol, limit=5)` to get highest-performing strategies for this symbol
2. **Get Strategy Signals**: For each strategy, call `get_strategy_signal(strategy_id, symbol)` to get current signal
3. **Get Market Context**: Call `get_current_price(symbol)` and `get_volatility(symbol, timeframe="1h")`
4. **Synthesize Signal**:
   - Count bullish/bearish/neutral signals
   - Calculate confidence based on consensus strength
   - Generate reasoning explaining the decision
5. **Publish Signal**: Send to Redis `channel:raw-signals`

### Confidence Calculation

```python
def calculate_confidence(strategies: list[StrategySignal]) -> float:
    """
    Confidence based on strategy consensus and individual scores.

    - 5/5 agree: 0.90-0.95 (modified by avg strategy score)
    - 4/5 agree: 0.75-0.85
    - 3/5 agree: 0.60-0.70
    - 2/5 agree: 0.45-0.55
    - 1/5 agree: 0.30-0.40
    """
    bullish = sum(1 for s in strategies if s.signal == "BUY")
    bearish = sum(1 for s in strategies if s.signal == "SELL")
    total = len(strategies)

    max_agreement = max(bullish, bearish, total - bullish - bearish)
    consensus_ratio = max_agreement / total

    avg_score = sum(s.score for s in strategies) / total

    # Base confidence from consensus
    if consensus_ratio >= 0.8:
        base = 0.85
    elif consensus_ratio >= 0.6:
        base = 0.70
    else:
        base = 0.50

    # Adjust by average strategy score
    confidence = base * (0.8 + 0.2 * avg_score)

    return min(0.95, max(0.30, confidence))
```

## MCP Tools Used

### strategy-mcp

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_top_strategies` | `symbol: string, limit: int` | Array of top strategies with scores |
| `get_strategy_signal` | `strategy_id: string, symbol: string` | Current signal for strategy |
| `get_strategy_consensus` | `symbol: string` | Aggregated consensus across all strategies |

### market-data-mcp

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_current_price` | `symbol: string` | Current price and 24h change |
| `get_candles` | `symbol: string, timeframe: string, limit: int` | OHLCV candles |
| `get_volatility` | `symbol: string, timeframe: string` | Volatility metrics |

## Skills

### analyze-symbol

```markdown
# Skill: analyze-symbol

## Purpose
Perform comprehensive analysis of a trading symbol using available MCP tools.

## Workflow
1. Fetch top 5 strategies for the symbol
2. Get current signal from each strategy
3. Gather market context (price, volume, volatility)
4. Synthesize findings into a trading signal

## Output Format
Structured JSON signal with confidence and reasoning.
```

### detect-patterns

```markdown
# Skill: detect-patterns

## Purpose
Identify technical patterns in recent price action.

## Patterns to Detect
- Trend: Uptrend, Downtrend, Sideways
- Momentum: Accelerating, Decelerating, Reversal
- Volume: Breakout confirmation, Divergence
- Support/Resistance: Near key levels

## Output
Pattern summary to include in signal reasoning.
```

## Constraints

- Must complete analysis in < 10 seconds per symbol
- Must work with any OpenRouter-supported model
- Publishes to Redis channel: `channel:raw-signals`
- Signal format must match schema exactly
- Must handle tool failures gracefully (skip strategy, log error)

## Configuration

```json
{
  "name": "signal-generator",
  "model": "google/gemini-3.0-flash",
  "mcp_servers": {
    "strategy-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.strategy_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    },
    "market-data-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.market_data_mcp"],
      "env": {
        "INFLUXDB_URL": "${INFLUXDB_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "output": {
    "redis_channel": "channel:raw-signals"
  },
  "limits": {
    "timeout_seconds": 10,
    "max_strategies": 5,
    "retry_count": 2
  }
}
```

## Acceptance Criteria

- [ ] Agent analyzes symbol using MCP tools (strategy + market data)
- [ ] Raw signal published to Redis within 10 seconds
- [ ] Reasoning includes strategy breakdown with individual signals
- [ ] Works with Claude, GPT-4, Llama via OpenRouter
- [ ] Handles tool failures gracefully (partial results if some tools fail)
- [ ] Signal format matches schema exactly
- [ ] Confidence calculation follows defined formula

## File Structure

```
agents/signal-generator/
├── .opencode/
│   └── config.json
├── skills/
│   ├── analyze-symbol/
│   │   └── SKILL.md
│   └── detect-patterns/
│       └── SKILL.md
├── prompts/
│   └── system.md
└── tests/
    └── test_signal_generator.py
```

## Example Invocation

```bash
# Run signal generator for a single symbol
opencode --config agents/signal-generator/.opencode/config.json \
  --prompt "Analyze ETH/USD and generate a trading signal"

# Run for multiple symbols (via Task tool internally)
opencode --config agents/signal-generator/.opencode/config.json \
  --prompt "Analyze these symbols: ETH/USD, BTC/USD, SOL/USD"
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| strategy-mcp unavailable | Use cached strategies, reduce confidence by 20% |
| market-data-mcp unavailable | Skip market context, note in reasoning |
| All tools fail | Generate HOLD signal with 0.30 confidence |
| Timeout exceeded | Publish partial signal, log warning |
| Invalid symbol | Return error event, skip symbol |

## Metrics

- `signal_generator_signals_total` - Signals generated by action
- `signal_generator_latency_ms` - Time to generate signal
- `signal_generator_tool_calls_total` - Tool calls by tool name
- `signal_generator_errors_total` - Errors by type
- `signal_generator_confidence_histogram` - Distribution of confidence scores
