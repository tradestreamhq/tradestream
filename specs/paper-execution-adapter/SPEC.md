# Paper Execution Adapter

Status: Proposed
Owner: TradeStream / Market Expansion

## Problem

TradeStream can ingest crypto market data, discover strategy candidates, and run backtests, but market expansion needs a repeatable bridge from signal generation to realistic paper trading before any live execution is considered. Backtest-only PnL is not sufficient for capital decisions because it usually under-models fees, spread, book impact, latency, venue constraints, and replay drift.

This spec defines the adapter and ledger boundary for paper execution. It is deliberately execution-shaped, but it must not place live orders.

## Goals

- Accept normalized trade intents from signal-generating services or agents.
- Simulate fills with venue-specific fees, spread, book depth, and latency assumptions.
- Persist a replayable paper-trade ledger with enough provenance to audit PnL.
- Support crypto first, then equities and forex through the same interface.
- Make promotion to live trading impossible without a separate, explicit live-execution adapter and principal approval.

## Non-Goals

- No live broker API keys.
- No capital movement.
- No margin, leverage, options, futures, or DEX execution in the first implementation.
- No strategy-specific shortcuts inside the paper execution layer.

## Core Concepts

### Trade Intent

A normalized request from a strategy or agent:

```json
{
  "intent_id": "uuid",
  "strategy_id": "strategy-or-agent-id",
  "instrument": "BTC-USD",
  "asset_class": "crypto",
  "venue": "coinbase",
  "side": "buy",
  "order_type": "market",
  "quantity": "0.001",
  "max_notional_usd": "100.00",
  "signal_timestamp_utc": "2026-06-10T00:00:00Z",
  "rationale_ref": "agent_decision_id-or-signal-id"
}
```

### Market Snapshot

A reproducible view used by the simulator:

- Best bid/ask.
- Order-book levels when available.
- Last trade and candle context.
- Venue fee schedule version.
- Data source and freshness timestamp.

### Paper Fill

The simulated execution result:

- Fill price and quantity.
- Fees in quote currency.
- Slippage versus arrival mid.
- Latency assumption used.
- Partial-fill or reject reason.
- Snapshot reference.

### Ledger Entry

The immutable audit record joining intent, snapshot, fill, strategy, and PnL state.

Ledger entries must be append-only. Corrections happen through reversal/correction entries, not mutation.

## Adapter Interface

The first implementation should expose a small service/API boundary:

- `submit_intent(intent) -> accepted/rejected`
- `simulate_pending(now_utc) -> fills[]`
- `get_ledger(strategy_id?, instrument?, since?) -> entries[]`
- `get_pnl(strategy_id?, instrument?, since?) -> summary`
- `replay(intent_id | ledger_range) -> replay_result`

The adapter must be deterministic when replaying against the same snapshot, fee schedule, and latency model.

## Promotion Gate

A strategy cannot be proposed for live execution unless paper execution records show:

- Positive net PnL after fees and modeled slippage.
- Bounded drawdown under the approved cap.
- Replay error within tolerance.
- No stale-data fills.
- No missing ledger provenance.
- A written live-capital proposal reviewed by Patrick.

## First Venue

Use Coinbase for crypto-shaped paper execution because it aligns with the existing TradeStream crypto pipeline and the broader agent ecosystem. The first adapter may use stored book/candle data only; direct WebSocket book capture can follow when the ledger contract is proven.

## Testing Requirements

- Unit tests for fee/slippage/latency calculations.
- Contract tests for accepted and rejected trade intents.
- Replay determinism tests.
- Ledger append-only tests.
- Multi-asset metadata tests for crypto 24/7, equities sessions, and forex sessions before adding those asset classes.

## Operational Requirements

- No live credentials in paper execution pods.
- Secrets, when eventually required for market data, must come through GitOps-managed secret references.
- Every paper fill must include a request ID / trace ID.
- Metrics should include accepted intents, rejected intents, simulated fills, stale-data rejects, replay failures, and net paper PnL.
