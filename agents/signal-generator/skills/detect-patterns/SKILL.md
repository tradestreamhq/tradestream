---
name: "detect-patterns"
description: "Identify technical patterns in recent price action — trend direction, momentum shifts, volume anomalies, and support/resistance levels — to enrich trading signal reasoning. Use when the signal-generator agent needs pattern-based context for a symbol."
---

# Detect Patterns

Analyze recent price action to identify technical patterns that enrich signal reasoning with trend, momentum, volume, and support/resistance context.

## Workflow

1. **Fetch candles**: Call `get_candles(symbol, timeframe="1h", limit=24)` for the last 24 hours of price data
2. **Analyze trend**: Compare highs and lows across candles to determine trend direction
3. **Calculate momentum**: Measure rate-of-change across candle intervals to detect acceleration or reversal
4. **Check volume**: Compare candle volumes against the 24h moving average to identify breakout confirmation or divergence
5. **Map support/resistance**: Extract recent swing highs/lows and assess proximity to current price

## Patterns to Detect

| Category | Pattern | Signal |
|----------|---------|--------|
| **Trend** | Uptrend | Higher highs and higher lows |
| | Downtrend | Lower highs and lower lows |
| | Sideways | Price confined within a narrow range |
| **Momentum** | Accelerating | Increasing rate of price change |
| | Decelerating | Decreasing rate of price change |
| | Reversal | Momentum shift between bullish and bearish |
| **Volume** | Breakout confirmation | Price move with above-average volume |
| | Divergence | Price and volume trending opposite directions |
| **S/R** | Near support | Price approaching or bouncing off support |
| | Near resistance | Price approaching or rejecting at resistance |
| | Breakout | Price breaking a key level with volume |

## Output Format

Return a pattern summary for inclusion in signal reasoning:

```json
{
  "trend": "uptrend|downtrend|sideways",
  "momentum": "accelerating|decelerating|reversal",
  "volume_pattern": "breakout_confirmation|divergence|normal",
  "support_resistance": "near_support|near_resistance|breakout|none",
  "pattern_confidence": 0.75,
  "summary": "Strong uptrend with accelerating momentum and volume confirmation"
}
```
