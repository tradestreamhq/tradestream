# Skill: detect-patterns

## Purpose
Identify technical patterns in recent price action to enrich signal reasoning.

## Patterns to Detect

### Trend Patterns
- **Uptrend**: Higher highs and higher lows in recent candles
- **Downtrend**: Lower highs and lower lows in recent candles
- **Sideways**: Price confined within a narrow range

### Momentum Patterns
- **Accelerating**: Increasing rate of price change
- **Decelerating**: Decreasing rate of price change
- **Reversal**: Momentum shift from bullish to bearish or vice versa

### Volume Patterns
- **Breakout confirmation**: Price move accompanied by above-average volume
- **Divergence**: Price moving in one direction while volume trends opposite

### Support/Resistance
- **Near support**: Price approaching or bouncing off a support level
- **Near resistance**: Price approaching or rejecting at a resistance level
- **Breakout**: Price breaking through a key level with volume

## Workflow
1. Fetch recent candles using `get_candles(symbol, timeframe="1h", limit=24)`
2. Analyze price action for trend direction
3. Calculate momentum indicators from candle data
4. Check volume patterns against moving averages
5. Identify support/resistance levels from recent highs/lows

## Output
Pattern summary to include in signal reasoning:

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
