# GA Core Extracted

The genetic algorithm core has been extracted to a dedicated repository:

**New repo**: [`tradestreamhq/tradestream-ga`](https://github.com/tradestreamhq/tradestream-ga)
(Currently at [`pselamy/tradestream-ga`](https://github.com/pselamy/tradestream-ga) pending org transfer)

## What moved

The following packages were migrated to the new repo:

- `com.verlumen.tradestream.discovery` — GA discovery pipeline (Jenetics + Beam/Flink)
- `com.verlumen.tradestream.strategies` — All 63 strategy implementations (TA4J)
- `com.verlumen.tradestream.backtesting` — Backtesting logic (walk-forward, Monte Carlo)
- `com.verlumen.tradestream.backtestingservice` — gRPC backtesting service
- `com.verlumen.tradestream.marketdata` — Candle data fetching (InfluxDB)
- `com.verlumen.tradestream.kafka` — Kafka producer/consumer
- `com.verlumen.tradestream.postgres` — PostgreSQL persistence
- `com.verlumen.tradestream.ta4j` — Custom TA4J extensions
- Supporting packages: `influxdb`, `instruments`, `signals`, `sql`, `time`, `http`, `execution`

## Proto files migrated

- `discovery.proto`
- `backtesting.proto`
- `strategies.proto`
- `marketdata.proto`

## New gRPC interface

The new repo exposes a `GAService` (defined in `ga_service.proto`) with three RPCs:

| RPC | Description |
|-----|-------------|
| `SubmitStrategySpec` | Start a GA optimization run |
| `GetTopStrategies` | Get top N strategies from a run |
| `GetPerformance` | Get performance metrics for a strategy |

The existing `BacktestingService` is also available in the new repo.

## How to consume

TypeScript services should connect to the GA service via gRPC using the protos published in the `tradestream-ga` repo. Kafka topic contracts remain unchanged.
