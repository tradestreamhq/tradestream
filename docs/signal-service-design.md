# Signal Service Product Design

## Overview

TradeStream's Signal Service generates, scores, and delivers trading signals to users across multiple channels. This document covers signal types, delivery architecture, user subscription model, filtering/routing, and user journey flows.

## Signal Types

### Action Types

| Action | Description |
|--------|-------------|
| **BUY** | Enter a long position |
| **SELL** | Exit long or enter short position |
| **HOLD** | No action — maintain current position |
| **CLOSE_LONG** | Exit an existing long position |
| **CLOSE_SHORT** | Exit an existing short position |

### Opportunity Tiers

Signals are scored (0–100) by the Opportunity Scorer Agent and assigned a tier:

| Tier | Score Range | Urgency |
|------|------------|---------|
| **HOT** | > 80 | High — immediate action recommended |
| **GOOD** | 60–80 | Moderate — worth reviewing |
| **NEUTRAL** | 40–60 | Low — informational only |
| **LOW** | < 40 | Minimal — typically filtered out |

### Signal Payload

```json
{
  "signal_id": "uuid",
  "symbol": "BTC/USD",
  "action": "BUY",
  "confidence": 0.82,
  "score": 85,
  "tier": "HOT",
  "reasoning": "7/10 strategies agree on bullish momentum...",
  "strategy_breakdown": [
    {"strategy_type": "RSI_REVERSAL", "signal": "BUY", "confidence": 0.89},
    {"strategy_type": "MACD_CROSS", "signal": "BUY", "confidence": 0.85}
  ],
  "stop_loss": 64200.00,
  "take_profit": 67800.00,
  "price": 65500.00,
  "timeframe": "1h",
  "created_at": "2026-03-12T10:30:00Z"
}
```

## Architecture

### Signal Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Signal Generator │────▶│ Opportunity      │────▶│ Signal MCP       │
│ Agent            │     │ Scorer Agent     │     │ Server           │
│ (per symbol,     │     │ (score + tier)   │     │ (store + publish)│
│  every 60s)      │     │                  │     │                  │
└─────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                          │
                                           ┌──────────────┼──────────────┐
                                           │              │              │
                                           ▼              ▼              ▼
                                      PostgreSQL     Redis Pub/Sub   Agent Decisions
                                      (signals)     (signals:BTC/USD) (audit trail)
                                           │              │
                                           │              ▼
                                           │    ┌──────────────────┐
                                           │    │ Notification     │
                                           │    │ Service          │
                                           │    │ (filter + route) │
                                           │    └────────┬─────────┘
                                           │             │
                                           │    ┌────────┼────────┬──────────┐
                                           │    ▼        ▼        ▼          ▼
                                           │ Telegram  Discord   Slack    Web Push
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ UI Dashboard │
                                    │ (SSE stream) │
                                    └──────────────┘
```

### Key Components

| Component | Location | Role |
|-----------|----------|------|
| Signal Generator Agent | `services/signal_generator_agent/` | Analyzes top strategies via MCP tools, produces raw signals every 60s per symbol |
| Opportunity Scorer Agent | `services/opportunity_scorer_agent/` | Scores signals 0–100, assigns tier (HOT/GOOD/NEUTRAL/LOW) |
| Strategy Confidence Scorer | `services/strategy_confidence_scorer/` | Downweights strategies failing walk-forward validation |
| Signal MCP Server | `services/signal_mcp/` | Persists signals to PostgreSQL, publishes to Redis pub/sub |
| Notification Service | `services/notification_service/` | Subscribes to Redis, filters by user preferences, delivers to channels |
| Paper Trading Service | `services/paper_trading/` | Simulates trade execution from signals, tracks P&L |
| Orchestrator Agent | `services/orchestrator_agent/` | Coordinates the agent pipeline with circuit-breaker health monitoring |
| Agent Dashboard UI | `ui/agent-dashboard/` | Real-time signal stream via SSE, shows signals/decisions/tool calls |

### Storage

**PostgreSQL tables:**

- **`signals`** — Core signal data (action, confidence, price, stop_loss, take_profit, outcome, notification tracking)
- **`agent_decisions`** — Full audit trail of agent reasoning, tool calls, model used, latency, tokens
- **`paper_trades`** — Simulated trade execution linked to signals (entry/exit price, P&L, status)

**Redis:**

- Pub/sub channels: `signals:{symbol}` (e.g., `signals:BTC/USD`)
- Pattern subscription `signals:*` for consuming all signals

## Delivery Channels

### Channel Priority & Status

| Channel | Priority | Status | Integration |
|---------|----------|--------|-------------|
| Telegram Bot | P1 | Implemented | Bot API `/sendMessage`, HTML formatting |
| Discord Webhook | P1 | Implemented | Webhook embeds, color-coded by action |
| Slack (Bolt SDK) | P2 | Planned | Bolt SDK integration |
| Web Push / PWA | P2 | Planned | Web Push API |
| Email Digest | P3 | Planned | Aggregated summary, configurable frequency |

### Channel Formatting

**Telegram:**
- HTML with emojis (🟢 BUY, 🔴 SELL)
- Fields: Action, Confidence %, Opportunity Score, Summary

**Discord:**
- Embeds with color coding (green = BUY, red = SELL, gray = HOLD)
- Fields: Confidence, Expected Return, Strategy Consensus, Top Strategy

## User Subscription Model

### User Channel Preferences

Users configure per-channel delivery settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `channel` | telegram, discord, slack, push | — |
| `channel_id` | Platform-specific identifier | — |
| `enabled` | Channel on/off toggle | true |
| `is_primary` | Primary notification channel | false |
| `min_opportunity_score` | Minimum score threshold | 60 |
| `symbols` | Subscribed symbols (null = all) | null |
| `actions` | Subscribed actions (null = all) | null |
| `quiet_hours_start/end` | Do-not-disturb window | — |
| `timezone` | User timezone | UTC |

### Delivery Preferences

| Setting | Description | Default |
|---------|-------------|---------|
| `dedup_preference` | `primary_only`, `all_enabled`, `fallback_chain` | `primary_only` |
| `primary_channel` | Preferred channel for dedup | — |
| `fallback_order` | Channel priority list for fallback | — |
| `tier` | Subscription tier: free, pro, power | free |

### Deduplication Strategies

- **`primary_only`** (default) — Signal delivered to primary channel only
- **`all_enabled`** — Signal delivered to all enabled channels
- **`fallback_chain`** — Try primary, fall back to next channel on failure

Cross-channel dedup key: `signal_id + user_id` with 1-hour TTL.

### Rate Limits by Tier

| Channel | Free | Pro (2x) | Power (3x) |
|---------|------|----------|-------------|
| Telegram | 1/symbol/5min | 1/symbol/2.5min | 1/symbol/1.67min |
| Discord | 1/symbol/5min | 1/symbol/2.5min | 1/symbol/1.67min |
| Slack | 1/symbol/5min | 1/symbol/2.5min | 1/symbol/1.67min |
| Push | 10/hour | 20/hour | 30/hour |

## Signal Filtering & Routing

### Filtering Pipeline

Signals pass through these filters before delivery:

1. **Confidence threshold** — Minimum confidence (default 0.7)
2. **Tier filter** — Only deliver configured tiers (default: HOT, GOOD)
3. **Symbol filter** — Match user's subscribed symbols
4. **Action filter** — Match user's subscribed actions
5. **Quiet hours** — Suppress during user's do-not-disturb window
6. **Rate limiter** — Enforce per-tier rate limits
7. **Deduplication** — Cross-channel dedup by signal_id + user_id

### Retry & Dead Letter Queue

| Parameter | Value |
|-----------|-------|
| Max attempts | 6 |
| Backoff | Exponential (1s, 2s, 4s, 8s, 16s) |
| Total retry window | ~31 seconds |
| Non-retryable errors | Invalid token, blocked user, 401/403 |
| Failed deliveries | Moved to DLQ for manual review |

### Delivery Tracking

Every delivery is tracked with:
- Status progression: `pending → sent → delivered → read → failed`
- External message ID for platform-specific tracking
- Timestamps for sent/delivered/read
- Retry count and error messages

## User Journeys

### Journey 1: Subscribing to Signals

```
User                          System
 │                              │
 ├─ Opens Settings ────────────▶│
 │                              ├─ Shows channel options
 │◀─────────────────────────────┤   (Telegram, Discord, etc.)
 │                              │
 ├─ Connects Telegram ─────────▶│
 │  (links bot, verifies)       ├─ Stores channel_id
 │◀── Confirmation message ─────┤   Sets as primary
 │                              │
 ├─ Selects symbols ───────────▶│
 │  (BTC/USD, ETH/USD)          ├─ Updates symbols[]
 │                              │
 ├─ Sets minimum score ────────▶│
 │  (e.g., 70)                  ├─ Updates min_opportunity_score
 │                              │
 ├─ Sets quiet hours ──────────▶│
 │  (22:00 - 08:00 EST)         ├─ Updates quiet_hours + timezone
 │                              │
 ├─ Saves preferences ─────────▶│
 │                              ├─ Validates & persists
 │◀── "You're subscribed!" ─────┤
 │                              │
```

**Key screens:**

1. **Channel Connection** — OAuth or bot-link flow per platform. Telegram uses `/start` with a deep link; Discord uses webhook URL.
2. **Symbol Selector** — Multi-select from available instruments. Option for "All symbols."
3. **Filter Configuration** — Minimum score slider (0–100), tier checkboxes, action type toggles.
4. **Quiet Hours** — Time range picker with timezone selector.
5. **Delivery Mode** — Choose between primary-only, all channels, or fallback chain.

### Journey 2: Receiving a Signal

```
Signal Generator               System                         User
 │                              │                              │
 ├─ Emits BUY BTC/USD ────────▶│                              │
 │  confidence: 0.85            ├─ Opportunity Scorer          │
 │                              │  assigns score: 88, tier: HOT│
 │                              │                              │
 │                              ├─ Signal MCP stores to DB     │
 │                              ├─ Publishes to Redis          │
 │                              │  signals:BTC/USD             │
 │                              │                              │
 │                              ├─ Notification Service        │
 │                              │  receives from Redis         │
 │                              │                              │
 │                              ├─ Checks user preferences:    │
 │                              │  ✓ BTC/USD in symbols        │
 │                              │  ✓ Score 88 ≥ threshold 70   │
 │                              │  ✓ Not in quiet hours        │
 │                              │  ✓ Rate limit OK             │
 │                              │                              │
 │                              ├─ Sends Telegram message ────▶│
 │                              │  🟢 BUY BTC/USD              │── Receives push
 │                              │  Confidence: 85%             │   notification
 │                              │  Score: 88 (HOT)             │
 │                              │  "7/10 strategies bullish..." │
 │                              │                              │
 │                              ├─ Records delivery receipt    │
 │                              │  status: sent → delivered    │
 │                              │                              │
```

**Signal notification contains:**

- Action and symbol (BUY BTC/USD)
- Confidence percentage and opportunity score
- Tier badge (HOT / GOOD)
- Brief reasoning summary
- Strategy consensus breakdown
- Suggested stop-loss and take-profit levels

### Journey 3: Acting on a Signal

```
User                          System                         Market
 │                              │                              │
 ├─ Receives HOT signal ───────▶│                              │
 │  BUY BTC/USD @ $65,500       │                              │
 │                              │                              │
 ├─ Taps "View Details" ──────▶│                              │
 │                              ├─ Opens signal detail view    │
 │◀─────────────────────────────┤  - Full strategy breakdown   │
 │                              │  - Historical accuracy       │
 │                              │  - Risk parameters           │
 │                              │                              │
 │  Option A: Paper Trade       │                              │
 ├─ Taps "Paper Trade" ───────▶│                              │
 │                              ├─ POST /paper/execute         │
 │                              │  {signal_id, quantity}       │
 │                              ├─ Creates paper_trade record  │
 │                              │  entry_price: $65,500        │
 │◀── "Paper trade opened" ────┤                              │
 │                              │                              │
 │  ... time passes ...         │              ┌───────────────┤
 │                              │◀─────────────┤ Price moves   │
 │                              ├─ Calculates unrealized P&L   │
 │◀── P&L update notification ─┤                              │
 │                              │                              │
 │  Option B: External Trade    │                              │
 ├─ Opens exchange app ────────▶│                              │
 │  Places real order           │                              │
 │  using signal parameters     │                              │
 │  (price, SL, TP)             │                              │
 │                              │                              │
 │  Option C: Dismiss           │                              │
 ├─ Dismisses signal ──────────▶│                              │
 │                              ├─ Logs dismissal in           │
 │                              │  agent_decisions             │
 │                              │                              │
```

**Key screens:**

1. **Signal Detail View** — Full breakdown: per-strategy signals, confidence scores, walk-forward validation status, historical accuracy for the strategy combination.
2. **Paper Trade Execution** — One-tap to simulate the trade. Shows entry price, suggested quantity, projected risk/reward.
3. **Portfolio Dashboard** — Active paper trades, realized/unrealized P&L, win rate, signal accuracy over time.
4. **Signal History** — Chronological list of past signals with outcomes (profit/loss/breakeven), filterable by symbol and tier.

## Wireframe Descriptions

### Screen 1: Signal Stream (Dashboard Home)

```
┌─────────────────────────────────────────┐
│  TradeStream              [⚙ Settings]  │
├─────────────────────────────────────────┤
│  Signal Stream                          │
│  ┌─────────────────────────────────┐    │
│  │ 🟢 BUY BTC/USD        10:30 AM │    │
│  │ Score: 88 (HOT)   Conf: 85%    │    │
│  │ "Bullish consensus across 7/10  │    │
│  │  strategies..."                 │    │
│  │ [View Details]  [Paper Trade]   │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ 🔴 SELL ETH/USD       10:15 AM │    │
│  │ Score: 72 (GOOD)  Conf: 78%    │    │
│  │ "Bearish divergence detected..."│    │
│  │ [View Details]  [Paper Trade]   │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ── Filter: [All ▾] [HOT+GOOD ▾] ──    │
│                                         │
├─────────────────────────────────────────┤
│  [Signals]  [Portfolio]  [Settings]     │
└─────────────────────────────────────────┘
```

### Screen 2: Signal Detail

```
┌─────────────────────────────────────────┐
│  ← Back            Signal Detail        │
├─────────────────────────────────────────┤
│  🟢 BUY BTC/USD                        │
│  Score: 88 (HOT)   Confidence: 85%     │
│  Price: $65,500   Time: 10:30 AM       │
│                                         │
│  Risk Parameters                        │
│  ├─ Stop Loss:    $64,200 (-2.0%)      │
│  ├─ Take Profit:  $67,800 (+3.5%)      │
│  └─ Risk/Reward:  1:1.75              │
│                                         │
│  Strategy Breakdown                     │
│  ├─ RSI_REVERSAL    BUY   89%  ████░   │
│  ├─ MACD_CROSS      BUY   85%  ████░   │
│  ├─ VOLUME_BREAKOUT BUY   80%  ████░   │
│  ├─ BOLLINGER_BAND  BUY   76%  ███░░   │
│  └─ MEAN_REVERSION  SELL  65%  ███░░   │
│                                         │
│  Reasoning                              │
│  "7 of 10 strategies show bullish       │
│   consensus. Volume 1.8x above 20-day  │
│   average. RSI recovering from 32..."   │
│                                         │
│  Historical Accuracy: 71% (last 30d)    │
│                                         │
│  [Paper Trade]     [Dismiss]            │
└─────────────────────────────────────────┘
```

### Screen 3: Notification Preferences

```
┌─────────────────────────────────────────┐
│  ← Back          Notification Settings  │
├─────────────────────────────────────────┤
│                                         │
│  Connected Channels                     │
│  ┌─────────────────────────────────┐    │
│  │ ✅ Telegram    @tradestream_bot │    │
│  │    ★ Primary channel            │    │
│  │    [Disconnect]                 │    │
│  ├─────────────────────────────────┤    │
│  │ ✅ Discord     #trading-signals │    │
│  │    [Set as Primary]             │    │
│  ├─────────────────────────────────┤    │
│  │ ○  Slack       [Connect]        │    │
│  │ ○  Web Push    [Enable]         │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Delivery Mode                          │
│  (●) Primary only                       │
│  ( ) All channels                       │
│  ( ) Fallback chain                     │
│                                         │
│  Symbols: [BTC/USD ✕] [ETH/USD ✕] [+]  │
│                                         │
│  Minimum Score: ──────●── 70            │
│  Tiers: [✓ HOT] [✓ GOOD] [○ NEUTRAL]   │
│                                         │
│  Quiet Hours: 22:00 — 08:00 EST        │
│                                         │
│  [Save Preferences]                     │
└─────────────────────────────────────────┘
```

## Outcome Tracking

Signals are tracked through their full lifecycle:

| Outcome | Description |
|---------|-------------|
| **PROFIT** | Signal direction matched market movement |
| **LOSS** | Signal direction was incorrect |
| **BREAKEVEN** | No material P&L |
| **PENDING** | Position still open / not yet resolved |
| **CANCELLED** | Signal was dismissed or expired |

Metrics exposed via Signal MCP:
- **`get_paper_pnl()`** — Total P&L, win rate, average return, open positions
- **`get_signal_accuracy(lookback_hours)`** — Accuracy rate comparing signal direction vs actual outcome
