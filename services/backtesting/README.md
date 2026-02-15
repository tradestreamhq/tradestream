# VectorBT Backtesting Microservice

High-performance backtesting service using VectorBT for vectorized operations.

## Overview

This microservice provides backtesting capabilities optimized for:

- **Genetic Algorithm Optimization**: Fast evaluation of thousands of strategy variants
- **Vectorized Computations**: 10-100x faster than event-driven backtesting
- **Full Indicator Coverage**: 40+ indicators matching ta4j functionality

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py --port 8080

# Run tests
pytest tests/ -v
```

### Docker

```bash
# Build image
docker build -t tradestream/backtesting .

# Run container
docker run -p 8080:8080 tradestream/backtesting
```

## API

### POST /backtest

Run a single backtest.

```json
{
  "candles": [
    {"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
    ...
  ],
  "strategy": {
    "strategyName": "MACD_CROSSOVER",
    "parameters": {
      "shortEmaPeriod": 12,
      "longEmaPeriod": 26,
      "signalPeriod": 9
    }
  }
}
```

Response:

```json
{
  "cumulativeReturn": 0.15,
  "annualizedReturn": 0.25,
  "sharpeRatio": 1.5,
  "sortinoRatio": 2.1,
  "maxDrawdown": 0.08,
  "volatility": 0.02,
  "winRate": 0.55,
  "profitFactor": 1.8,
  "numberOfTrades": 42,
  "averageTradeDuration": 15.5,
  "strategyScore": 0.72
}
```

### POST /batch

Run multiple backtests with different parameter sets (optimized for GA).

### GET /health

Health check endpoint.

### GET /indicators

List available indicators.

## Supported Strategies

- SMA_RSI
- MACD_CROSSOVER
- EMA_MACD
- SMA_EMA_CROSSOVER
- RSI_EMA_CROSSOVER
- BOLLINGER_BANDS
- ADX_STOCHASTIC
- DOUBLE_EMA_CROSSOVER
- TRIPLE_EMA_CROSSOVER

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    gRPC / HTTP API                      │
├─────────────────────────────────────────────────────────┤
│                  BacktestingService                     │
├─────────────────────────────────────────────────────────┤
│                   VectorBTRunner                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  Strategy   │  │  Indicator  │  │    Portfolio    │ │
│  │  Signals    │  │  Registry   │  │    Simulation   │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                   VectorBT / NumPy                      │
│                  (Numba JIT Compiled)                   │
└─────────────────────────────────────────────────────────┘
```

## Performance

Benchmarks (1000 bars, 100 parameter combinations):

| Operation            | Time   | Speedup vs Event-Driven |
| -------------------- | ------ | ----------------------- |
| Single backtest      | ~5ms   | ~20x                    |
| Batch (100 variants) | ~200ms | ~50x                    |

## Related Issues

- Issue #1626: Create VectorBT gRPC Backtesting Microservice
- ADR #1625: Migrate Backtesting Engine from ta4j to VectorBT
