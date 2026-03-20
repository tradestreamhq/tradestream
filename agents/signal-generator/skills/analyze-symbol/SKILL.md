# Skill: analyze-symbol

## Purpose
Perform comprehensive analysis of a trading symbol using available MCP tools.

## Workflow
1. Fetch top 5 strategies for the symbol using `get_top_strategies(symbol, limit=5)`
2. Get current signal from each strategy using `get_strategy_signal(strategy_id, symbol)`
3. Gather market context: `get_current_price(symbol)` and `get_volatility(symbol, timeframe="1h")`
4. Synthesize findings into a trading signal:
   - Count bullish/bearish/neutral signals
   - Calculate confidence based on consensus strength
   - Generate reasoning explaining the decision

## Output Format
Structured JSON signal with confidence and reasoning:

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
- If strategy MCP fails: retry 3x, then use cached strategies, reduce confidence by 20%
- If market data MCP fails: retry 3x, skip market context, reduce confidence by 10%
- If all tools fail: generate HOLD signal with 0.30 confidence
