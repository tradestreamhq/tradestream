# Configuration-Driven Strategies

**ID**: SPEC-001

## Goal
Trading strategies are defined entirely through YAML configuration files, with no Java code changes required to add or modify strategies.

## Target Behavior

### Strategy Definition
Strategies are defined in YAML files under `/src/main/resources/strategies/`. Each file specifies:

- **Metadata**: name, description, complexity level, parameter message type
- **Indicators**: Technical indicators (SMA, EMA, RSI, MACD, etc.) with configurable parameters
- **Entry/Exit Conditions**: Rules using crossovers, thresholds, and indicator comparisons
- **Parameters**: Tunable values with type, min/max bounds, and defaults

Example:
```yaml
name: SMA_EMA_CROSSOVER
description: Simple vs Exponential Moving Average crossover
complexity: SIMPLE
parameterMessageType: com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters

indicators:
  - id: sma
    type: SMA
    params:
      period: "${smaPeriod}"
  - id: ema
    type: EMA
    params:
      period: "${emaPeriod}"

entryConditions:
  - type: CROSSED_UP
    indicator: ema
    params:
      other: sma

exitConditions:
  - type: CROSSED_DOWN
    indicator: ema
    params:
      other: sma

parameters:
  - name: smaPeriod
    type: INTEGER
    min: 5
    max: 50
    defaultValue: 20
  - name: emaPeriod
    type: INTEGER
    min: 5
    max: 50
    defaultValue: 10
```

### Runtime Discovery
Strategies are auto-discovered from the classpath at startup. The `StrategyRegistry` provides unified access to all available strategies. No code changes are required to register new strategies.

### Indicator & Rule Support
`IndicatorRegistry` maps 30+ indicator types to Ta4j implementations. `RuleRegistry` maps 15+ condition types to Ta4j rule constructors. New indicator/rule types are added to registries without touching strategy configs.

### Supported Indicator Types
ADX, ATR, Bollinger Bands (upper/middle/lower), CCI, CMO, DEMA, DPO, EMA, HMA, Ichimoku, KAMA, MACD, MFI, OBV, Parabolic SAR, Pivot Points, ROC, RSI, SMA, Stochastic, TEMA, TRIX, Ultimate Oscillator, VWAP, Williams %R, WMA, ZLEMA

### Supported Condition Types
CROSSED_UP, CROSSED_DOWN, OVER, UNDER, OVER_CONSTANT, UNDER_CONSTANT, IS_RISING, IS_FALLING, AND, OR, NOT, GAIN_THRESHOLD, LOSS_THRESHOLD, STOP_LOSS, STOP_GAIN

## Constraints

- **Backward Compatibility**: Existing proto parameter messages continue to work
- **Performance**: Strategy construction adds no measurable latency to backtesting
- **Validation**: Invalid configs fail fast with clear error messages
- **Type Safety**: Parameter types (INTEGER, DOUBLE) are validated at load time

## Non-Goals

- Runtime strategy hot-reloading (restart required for config changes)
- GUI-based strategy builder
- Strategy versioning within configs
- Migration of custom/experimental strategies that require programmatic logic

## Acceptance Criteria

- [ ] All 70+ production strategies have YAML config equivalents
- [ ] `StrategySpecs.kt` static registry is removed
- [ ] Strategy discovery pipeline uses `StrategyRegistry.fromClasspath()`
- [ ] Adding a new strategy requires only: YAML file + proto parameter message
- [ ] All config-based strategies pass existing integration tests
- [ ] Documentation covers full config syntax and all supported indicators/rules

## Implementing Issues

| Issue | Status | Description |
|-------|--------|-------------|
| #1700 | merged | Refactor config strategy enum |

## Notes

Infrastructure is complete: `StrategyConfigLoader`, `ConfigurableStrategyFactory`, `IndicatorRegistry`, `RuleRegistry`. Documentation exists at `docs/strategies/adding-new-strategy.md`.
