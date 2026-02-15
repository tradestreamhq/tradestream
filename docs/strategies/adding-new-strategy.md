# Adding a New Strategy

This guide explains how to add a new trading strategy to TradeStream using the YAML configuration system.

## Overview

Strategies in TradeStream are defined in YAML configuration files and loaded at runtime via `StrategyRegistry`. This enables adding new strategies without code changes.

## Steps to Add a New Strategy

### 1. Create the Parameter Message (if needed)

If your strategy uses parameters not covered by existing proto messages, add a new `*Parameters` message to `protos/strategies.proto`:

```protobuf
message MyNewStrategyParameters {
  int32 shortPeriod = 1;
  int32 longPeriod = 2;
  double threshold = 3;
}
```

Then rebuild the proto bindings:

```bash
bazel build //protos:strategies_java_proto
```

### 2. Create the YAML Strategy File

Create a new YAML file in `src/main/resources/strategies/`:

```yaml
# src/main/resources/strategies/my_new_strategy.yaml

name: MY_NEW_STRATEGY
description: Description of what this strategy does
complexity: SIMPLE # SIMPLE, MEDIUM, or COMPLEX
parameterMessageType: com.verlumen.tradestream.strategies.MyNewStrategyParameters

indicators:
  - id: shortEma
    type: EMA
    input: close
    params:
      period: "${shortPeriod}"
  - id: longEma
    type: EMA
    input: close
    params:
      period: "${longPeriod}"

entryConditions:
  - type: CROSSED_UP
    indicator: shortEma
    params:
      crosses: longEma

exitConditions:
  - type: CROSSED_DOWN
    indicator: shortEma
    params:
      crosses: longEma

parameters:
  - name: shortPeriod
    type: INTEGER
    min: 5
    max: 20
    defaultValue: 10
  - name: longPeriod
    type: INTEGER
    min: 20
    max: 50
    defaultValue: 30
  - name: threshold
    type: DOUBLE
    min: 0.0
    max: 1.0
    defaultValue: 0.5
```

### 3. Verify the Strategy Loads

Run the tests to ensure your strategy loads correctly:

```bash
bazel test //src/test/java/com/verlum/tradestream/strategies:StrategyRegistryTest
```

## YAML Configuration Reference

### Required Fields

| Field                  | Description                                   |
| ---------------------- | --------------------------------------------- |
| `name`                 | Unique strategy identifier (UPPER_SNAKE_CASE) |
| `parameterMessageType` | Fully-qualified proto message class name      |
| `indicators`           | List of technical indicators to use           |
| `entryConditions`      | Conditions that trigger entry signals         |
| `exitConditions`       | Conditions that trigger exit signals          |
| `parameters`           | Tunable parameters with ranges                |

### Optional Fields

| Field         | Description                | Default |
| ------------- | -------------------------- | ------- |
| `description` | Human-readable description | Empty   |
| `complexity`  | Strategy complexity level  | SIMPLE  |

### Indicator Types

The following indicator types are supported (from `IndicatorRegistry`):

| Type              | Description                           | Parameters                  |
| ----------------- | ------------------------------------- | --------------------------- |
| `SMA`             | Simple Moving Average                 | `period`                    |
| `EMA`             | Exponential Moving Average            | `period`                    |
| `DEMA`            | Double Exponential Moving Average     | `period`                    |
| `TEMA`            | Triple Exponential Moving Average     | `period`                    |
| `MACD`            | Moving Average Convergence Divergence | `shortPeriod`, `longPeriod` |
| `RSI`             | Relative Strength Index               | `period`                    |
| `STOCHASTIC_K`    | Stochastic Oscillator %K              | `period`                    |
| `STOCHASTIC_D`    | Stochastic Oscillator %D              | `period`, `smoothPeriod`    |
| `BOLLINGER_UPPER` | Bollinger Bands Upper                 | `period`, `deviation`       |
| `BOLLINGER_LOWER` | Bollinger Bands Lower                 | `period`, `deviation`       |
| `ATR`             | Average True Range                    | `period`                    |
| `ADX`             | Average Directional Index             | `period`                    |
| `CCI`             | Commodity Channel Index               | `period`                    |
| `MFI`             | Money Flow Index                      | `period`                    |
| `OBV`             | On-Balance Volume                     | (none)                      |
| `VWAP`            | Volume Weighted Average Price         | `period`                    |
| `SAR`             | Parabolic SAR                         | `start`, `increment`, `max` |

### Condition Types

The following condition types are supported (from `RuleRegistry`):

| Type           | Description                       | Parameters       |
| -------------- | --------------------------------- | ---------------- |
| `CROSSED_UP`   | Indicator crossed above reference | `crosses`        |
| `CROSSED_DOWN` | Indicator crossed below reference | `crosses`        |
| `OVER`         | Indicator is above threshold      | `threshold`      |
| `UNDER`        | Indicator is below threshold      | `threshold`      |
| `BETWEEN`      | Indicator is between thresholds   | `lower`, `upper` |
| `INCREASING`   | Indicator is increasing           | (none)           |
| `DECREASING`   | Indicator is decreasing           | (none)           |

### Parameter Types

| Type      | Description              | Range Fields                 |
| --------- | ------------------------ | ---------------------------- |
| `INTEGER` | Integer parameter        | `min`, `max`, `defaultValue` |
| `DOUBLE`  | Floating-point parameter | `min`, `max`, `defaultValue` |

## Examples

### Simple Moving Average Crossover

```yaml
name: SMA_EMA_CROSSOVER
description: SMA crosses EMA for trend detection
complexity: SIMPLE
parameterMessageType: com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters

indicators:
  - id: sma
    type: SMA
    input: close
    params:
      period: "${smaPeriod}"
  - id: ema
    type: EMA
    input: close
    params:
      period: "${emaPeriod}"

entryConditions:
  - type: CROSSED_UP
    indicator: sma
    params:
      crosses: ema

exitConditions:
  - type: CROSSED_DOWN
    indicator: sma
    params:
      crosses: ema

parameters:
  - name: smaPeriod
    type: INTEGER
    min: 10
    max: 50
    defaultValue: 20
  - name: emaPeriod
    type: INTEGER
    min: 5
    max: 30
    defaultValue: 10
```

### RSI with EMA Crossover

```yaml
name: RSI_EMA_CROSSOVER
description: RSI-based entry with EMA confirmation
complexity: MEDIUM
parameterMessageType: com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters

indicators:
  - id: rsi
    type: RSI
    input: close
    params:
      period: "${rsiPeriod}"
  - id: ema
    type: EMA
    input: close
    params:
      period: "${emaPeriod}"

entryConditions:
  - type: UNDER
    indicator: rsi
    params:
      threshold: 30
  - type: CROSSED_UP
    indicator: close
    params:
      crosses: ema

exitConditions:
  - type: OVER
    indicator: rsi
    params:
      threshold: 70

parameters:
  - name: rsiPeriod
    type: INTEGER
    min: 7
    max: 21
    defaultValue: 14
  - name: emaPeriod
    type: INTEGER
    min: 10
    max: 30
    defaultValue: 20
```

## Using Your Strategy

### In Discovery Requests

```kotlin
val request = StrategyDiscoveryRequest.newBuilder()
    .setStrategyName("MY_NEW_STRATEGY")  // Use the name from YAML
    .setSymbol("BTC/USD")
    .setStartTime(startTimestamp)
    .setEndTime(endTimestamp)
    .setTopN(10)
    .setGaConfig(GAConfig.newBuilder()
        .setPopulationSize(100)
        .setMaxGenerations(50)
        .build())
    .build()
```

### Checking Available Strategies

```kotlin
val registry = StrategyRegistry.fromClasspath()

// List all strategies
val names = registry.getSupportedStrategyNames()
println("Available strategies: $names")

// Check if your strategy is loaded
val isLoaded = registry.isSupported("MY_NEW_STRATEGY")
println("MY_NEW_STRATEGY loaded: $isLoaded")
```

## Best Practices

1. **Use descriptive names**: Strategy names should clearly indicate the pattern (e.g., `MACD_CROSSOVER`, `RSI_EMA_CROSSOVER`)

2. **Set reasonable parameter ranges**: The GA optimizer works within the min/max bounds - too narrow limits exploration, too wide wastes computation

3. **Start with SIMPLE complexity**: Mark complex multi-indicator strategies appropriately

4. **Include the proto message type**: The `parameterMessageType` must match an existing proto message

5. **Test locally first**: Run unit tests before deploying

## Troubleshooting

### Strategy Not Loading

- Verify YAML syntax is valid
- Check that `parameterMessageType` exists in `strategies.proto`
- Ensure indicator types are valid (see `IndicatorRegistry`)
- Ensure condition types are valid (see `RuleRegistry`)

### Parameter Validation Errors

- Verify `min` < `defaultValue` < `max`
- Check parameter names match the proto message field names

### Indicator Not Found

- Check the indicator type is supported
- Verify indicator `id` references are correct in conditions
