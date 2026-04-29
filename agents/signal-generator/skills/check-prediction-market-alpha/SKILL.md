---
name: "check-prediction-market-alpha"
description: "Query Polymarket and Kalshi prediction markets for event-driven alpha correlating with crypto movements. Use when analyzing major crypto assets (BTC, ETH, SOL), detecting unusual volatility, or performing daily macro context checks."
---

# Check Prediction Market Alpha

Query prediction markets for event-driven signals that may correlate with crypto market movements, enriching the signal-generator's reasoning with macro context.

## When to Use

- Before generating signals for major crypto assets (BTC, ETH, SOL)
- When analyzing assets tied to real-world events (regulatory, political)
- When unusual market volatility is detected
- Daily macro context check

## Workflow

### 1. Polymarket Insider Signals (Optional)

Fetch recent high-confidence insider alerts from the polymarket-insider-tracker API:

```
GET ${POLYMARKET_API}/api/alerts/recent?min_confidence=HIGH&limit=5
GET ${POLYMARKET_API}/api/markets/watchlist
```

- Look for fresh wallet activity, unusual sizing, and niche market entries
- Cross-reference alert categories with current trading symbols
- If unavailable, use cached data or skip this source

### 2. Kalshi Market Movements (Optional)

Check crypto-relevant prediction markets:

```
GET https://api.elections.kalshi.com/trade-api/v2/markets?status=open&series_ticker=FED
GET https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook
```

- **Fed rate decisions** (FED-*) — direct impact on risk assets
- **Regulatory events** (SEC*, CFTC*) — enforcement actions, rule changes
- **ETF approvals** (BTCETF*, ETHETF*) — institutional flow catalysts
- Flag significant price movements (>10% in 24h) or volume spikes

### 3. Synthesize

- Identify correlations between prediction market activity and crypto assets
- Assess event timing — how far out is the catalyst?
- Generate actionable insight for inclusion in signal reasoning
- Include data freshness indicators so downstream consumers know recency

## Constraints

- Cache results with configurable TTL (default 60 seconds)
- Both sources are optional — skill operates in degraded mode if either is unavailable
- Fail gracefully with baseline response if both sources are down
- Only invoke for major crypto assets (BTC, ETH, SOL)
