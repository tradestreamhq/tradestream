# VectorBT Backtesting Migration

## Goal
Migrate the backtesting engine from ta4j (Java) to VectorBT (Python) for faster, vectorized strategy evaluation that aligns with the platform's Python-first V2 architecture.

## Target Behavior

### Backtesting Engine
A Python-based backtesting service using VectorBT that:

- **Reads YAML strategy specs** from `/src/main/resources/strategies/` and generates entry/exit signals using the indicator and condition definitions
- **Runs vectorized backtests** using VectorBT's `Portfolio.from_signals()` for high-performance evaluation
- **Returns standardized metrics**: cumulative return, annualized return, Sharpe ratio, Sortino ratio, max drawdown, volatility, win rate, profit factor, number of trades, average trade duration, alpha, beta, strategy score
- **Supports batch evaluation** for genetic algorithm optimization of strategy parameters

### Architecture
```
┌─────────────────────────────────────────────────┐
│              gRPC Interface                      │
│   RunBacktest / RunBatchBacktest / WalkForward    │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           YAML Strategy Loader                   │
│   Reads strategy YAML → generates signals        │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│        VectorBT Runner (vectorbt_runner.py)       │
│   Portfolio.from_signals() → BacktestMetrics      │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│         Indicator Registry                       │
│   30+ indicators: SMA, EMA, RSI, MACD, ADX...    │
└─────────────────────────────────────────────────┘
```

### YAML Strategy Integration
The YAML strategy loader interprets strategy definitions and produces entry/exit signals:

1. **Indicator computation**: Each `indicators` entry is computed via the `IndicatorRegistry`
2. **Condition evaluation**: `entryConditions` and `exitConditions` are evaluated using operators like `OVER`, `UNDER`, `CROSSED_UP`, `CROSSED_DOWN`
3. **Parameter substitution**: `${paramName}` placeholders are replaced with runtime values or defaults from the `parameters` section

### Migration Strategy
- **Phase 1 (current)**: VectorBT service runs alongside ta4j — new backtests use VectorBT, existing Java pipeline unchanged
- **Phase 2**: YAML strategy loader enables all 40+ strategies to be backtested via VectorBT without per-strategy Python code
- **Phase 3**: Retire ta4j backtesting, VectorBT becomes the sole engine

## Constraints

- **Backward Compatibility**: ta4j-based backtesting must continue to work during migration; VectorBT is additive
- **Proto Compatibility**: gRPC interface uses existing `backtesting.proto` messages — no breaking changes
- **Performance**: VectorBT must be at least as fast as ta4j for single-strategy evaluation and significantly faster for batch evaluation
- **Metric Parity**: VectorBT must produce the same 13 metrics defined in `BacktestResult` proto

## Non-Goals

- Replacing the Java strategy implementation (ta4j rules/indicators) — those remain for live trading
- Real-time backtesting or streaming evaluation
- GUI visualization of backtest results (separate concern)
- Walk-forward optimization in Phase 1

## Acceptance Criteria

- [x] VectorBT backtesting service exists at `services/backtesting/`
- [x] Indicator registry supports 30+ indicator types matching ta4j coverage
- [x] gRPC service implements `RunBacktest` and `RunBatchBacktest` RPCs
- [x] Unit tests cover core runner, indicator calculations, and strategy execution
- [ ] YAML strategy loader can read strategy specs and generate entry/exit signals
- [ ] Integration test demonstrates end-to-end: YAML spec → VectorBT backtest → metrics
- [ ] Bazel build targets defined for all components
- [ ] OCI image configured for deployment

## Implementing Issues

| Issue | Status | Description |
|-------|--------|-------------|
| #1625 | open   | ADR + initial VectorBT backtesting framework |
| -     | done   | Core VectorBT runner with 9 hardcoded strategies |
| -     | done   | Indicator registry with 30+ indicators |
| -     | done   | gRPC service and Bazel build targets |

## Notes

### Why VectorBT over ta4j?

| Criteria | ta4j (Java) | VectorBT (Python) |
|----------|-------------|-------------------|
| Evaluation speed | Loop-based, single-threaded | Vectorized NumPy/Numba, 10-100x faster for batch |
| Language alignment | Java — separate from V2 Python services | Python — native to V2 architecture |
| Strategy definition | Requires Java code per strategy | Can interpret YAML specs dynamically |
| Ecosystem | Limited to JVM | Rich Python data science ecosystem (pandas, scipy, etc.) |
| GA optimization | Jenetics (Java) — separate process | Native batch evaluation for parameter sweep |

### Alternatives Considered
- **Backtrader (Python)**: Event-driven, not vectorized — slower for batch evaluation
- **Zipline (Python)**: Heavier, designed for equities, poor crypto support
- **Custom NumPy engine**: Maximum control but high maintenance burden
- **Keep ta4j**: Misaligns with Python-first V2 direction

### Dependencies
- `vectorbt>=0.26.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `numba>=0.57.0`
- Existing proto definitions in `protos/backtesting.proto`
- YAML strategy specs in `src/main/resources/strategies/`
