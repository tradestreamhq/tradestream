# Changelog

All notable changes to TradeStream will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Strategy Identification Migration Complete**: Migrated from `StrategyType` enum to string-based `strategy_name` field
  - Strategies are now identified by string names (e.g., "MACD_CROSSOVER") instead of enum values
  - Strategy specifications are loaded from YAML configuration files at runtime
  - `StrategyRegistry` provides runtime strategy lookup by name
  - Added `parameterMessageType` field to YAML schema for type-safe parameter deserialization
  - All 55+ strategies migrated to YAML configuration format

### Added

- `StrategyRegistry` class for runtime strategy discovery and lookup
- YAML-based strategy configuration system with `StrategyConfigLoader`
- Documentation for adding new strategies (`docs/strategies/adding-new-strategy.md`)

### Removed

- `StrategyType` enum from `strategies.proto` (replaced with string-based `strategy_name`)
- `strategy_type` field from `StrategyDiscoveryRequest` (replaced with `strategy_name`)
- Hardcoded strategy factory mappings (replaced with config-driven approach)

### Migration Notes

If you have external code that uses the old `StrategyType` enum:

1. Replace `StrategyType.MACD_CROSSOVER` with `"MACD_CROSSOVER"` string
2. Use `setStrategyName("MACD_CROSSOVER")` instead of `setStrategyType(StrategyType.MACD_CROSSOVER)`
3. Use `StrategyRegistry.getSpec("MACD_CROSSOVER")` for strategy lookup

Example migration:

```kotlin
// Before (deprecated)
val request = StrategyDiscoveryRequest.newBuilder()
    .setStrategyType(StrategyType.MACD_CROSSOVER)
    .build()

// After (current)
val request = StrategyDiscoveryRequest.newBuilder()
    .setStrategyName("MACD_CROSSOVER")
    .build()
```
