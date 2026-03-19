# Skill: Check Prediction Market Alpha

## Purpose
Check prediction markets (Polymarket, Kalshi) for event-driven alpha that may
correlate with crypto market movements.

## When to Use
- Before generating signals for major crypto assets (BTC, ETH)
- When analyzing assets tied to real-world events (regulatory, political)
- When unusual market volatility is detected
- Daily macro context check

## Workflow

### 1. Polymarket (Insider Signals) - Optional
Fetch recent high-confidence insider alerts from polymarket-insider-tracker API:
- Look for fresh wallet activity, unusual sizing, niche market entries
- Cross-reference alert categories with current trading symbols
- If unavailable, use cached data or skip this source

### 2. Kalshi (Market Movements) - Optional
Check crypto-relevant markets:
- Fed rate decisions (FED-*)
- Regulatory events (SEC*, CFTC*)
- ETF approvals (BTCETF*, ETHETF*)
- Look for significant price movements (>10% in 24h) or volume spikes
- If unavailable, use cached data or skip this source

### 3. Synthesize
- Identify correlations between prediction market activity and crypto assets
- Assess timing (how far out is the event?)
- Generate actionable insight for signal reasoning
- Include data freshness indicators

## API Endpoints

### Polymarket Insider Tracker
```
GET ${POLYMARKET_API}/api/alerts/recent?min_confidence=HIGH&limit=5
GET ${POLYMARKET_API}/api/markets/watchlist
```

### Kalshi
```
GET https://api.elections.kalshi.com/trade-api/v2/markets?status=open&series_ticker=FED
GET https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook
```

## Constraints
- Cache results using configurable TTL (default 60 seconds)
- Polymarket is optional - skill operates in degraded mode if unavailable
- Kalshi is optional - skill operates in degraded mode if unavailable
- Fail gracefully with baseline response if both sources unavailable
- Only invoke for major crypto assets (BTC, ETH, SOL)
