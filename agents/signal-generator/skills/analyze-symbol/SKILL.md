---
name: "analyze-symbol"
description: "Fetch top trading strategies, gather market context via MCP tools, and synthesize a BUY/SELL/HOLD signal with confidence scoring. Use when the signal-generator agent evaluates a symbol for trading opportunities."
---

# Analyze Symbol

Perform comprehensive analysis of a trading symbol by aggregating strategy signals and market context into a single actionable trading signal.

## Workflow

1. **Fetch strategies**: Call `get_top_strategies(symbol, limit=5)` to retrieve the highest-performing strategies for the symbol
2. **Collect signals**: For each strategy, call `get_strategy_signal(strategy_id, symbol)` to get its current BUY/SELL/HOLD recommendation
3. **Gather market context**: Call `get_current_price(symbol)` and `get_volatility(symbol, timeframe="1h")` for real-time conditions
4. **Synthesize signal**:
   - Count bullish/bearish/neutral signals across strategies
   - Calculate confidence (0.30–0.95) based on consensus strength and strategy scores
   - Generate reasoning explaining which strategies drove the decision

## Signal Decision Rules

- **BUY**: Majority bullish AND market context supports upside
- **SELL**: Majority bearish AND market context supports downside
- **HOLD**: No clear consensus OR conflicting signals — lean HOLD unless market context is decisive

## Output Format

Return structured JSON matching this schema:

```json
{
  "signal_id": "sig-<uuid>",
  "symbol": "<symbol>",
  "action": "BUY|SELL|HOLD",
  "confidence": 0.82,
  "strategies_analyzed": 5,
  "strategies_bullish": 4,
  "strategies_bearish": 1,
  "strategies_neutral": 0,
  "top_strategy": {
    "name": "RSI_REVERSAL",
    "score": 0.89,
    "signal": "BUY",
    "parameters": {}
  },
  "strategy_breakdown": [
    {"name": "RSI_REVERSAL", "signal": "BUY", "score": 0.89}
  ],
  "reasoning": "Strong consensus among top strategies...",
  "market_context": {
    "current_price": 2450.50,
    "price_change_1h": 0.023,
    "volume_ratio": 1.45,
    "volatility_1h": 0.018
  },
  "timestamp": "2025-02-01T12:34:56Z"
}
```

## Error Handling

- **Strategy MCP fails**: Retry 3x, then fall back to cached strategies — reduce confidence by 20%
- **Market data MCP fails**: Retry 3x, skip market context section — reduce confidence by 10%
- **All tools fail**: Generate HOLD signal with 0.30 confidence and note degraded data in reasoning
