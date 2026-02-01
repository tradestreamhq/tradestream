# Prediction Market Integration Specification

## Goal

Integrate prediction market signals (Polymarket, Kalshi) as alpha sources via skills, enabling agents to incorporate event-driven intelligence into trading decisions.

## Why Prediction Markets?

Prediction markets aggregate informed opinions about future events. They can provide:
- **Insider signals**: Wallet forensics on Polymarket can detect informed money
- **Event timing**: Kalshi provides probabilities for regulatory decisions, Fed rates, etc.
- **Cross-market correlation**: Crypto often moves on macro events that prediction markets price

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRADESTREAM AGENTS                                                 │
│                                                                     │
│  Signal Generator Agent                                             │
│       │                                                             │
│       ├──► strategy-mcp (internal)                                  │
│       ├──► market-data-mcp (internal)                               │
│       └──► SKILL: check-prediction-market-alpha                     │
│                    │                                                │
└────────────────────│────────────────────────────────────────────────┘
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
┌────────────────────┐  ┌────────────────────┐
│  POLYMARKET        │  │  KALSHI            │
│  INSIDER TRACKER   │  │  API               │
│  (separate repo)   │  │  (kalshi.com/api)  │
│                    │  │                    │
│  /api/alerts/...   │  │  /markets/...      │
│  /api/wallets/...  │  │  /events/...       │
└────────────────────┘  └────────────────────┘
```

## Prediction Market Sources

### Polymarket (via polymarket-insider-tracker)

| Endpoint | Purpose | Data |
|----------|---------|------|
| `/api/alerts/recent` | Suspicious wallet activity | Wallet, market, confidence, timing |
| `/api/wallets/watchlist` | Known insider wallets | Wallet addresses, history |
| `/api/markets/watchlist` | Markets with insider signals | Market IDs, alert counts |

### Kalshi (Official API)

| Endpoint | Purpose | Data |
|----------|---------|------|
| `GET /markets` | List active markets | Tickers, prices, volume |
| `GET /markets/{ticker}/orderbook` | Current prices + volume | Bid/ask, depth |
| `GET /events/{event_ticker}` | Event details | Series, settlement dates |

## Why Skill > MCP for This Use Case

| Aspect | MCP Tool | Skill |
|--------|----------|-------|
| **Abstraction Level** | Low (single API call) | High (workflow with reasoning) |
| **Context** | None | Full conversation context |
| **Output** | Raw JSON | Interpreted analysis |
| **Best For** | Frequent atomic queries | Complex multi-step analysis |

For prediction markets, we want:
- Contextual reasoning about *why* alerts matter for crypto
- Multi-source synthesis (Polymarket + Kalshi)
- Selective invocation (only when relevant)
- Richer natural language output

## Skill Definition

### check-prediction-market-alpha/SKILL.md

```markdown
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

### 1. Polymarket (Insider Signals)
Fetch recent high-confidence insider alerts from polymarket-insider-tracker API:
- Look for fresh wallet activity, unusual sizing, niche market entries
- Cross-reference alert categories with current trading symbols

### 2. Kalshi (Market Movements)
Check crypto-relevant markets:
- Fed rate decisions (FED-*)
- Regulatory events (SEC*, CFTC*)
- ETF approvals (BTCETF*, ETHETF*)
- Look for significant price movements (>10% in 24h) or volume spikes

### 3. Synthesize
- Identify correlations between prediction market activity and crypto assets
- Assess timing (how far out is the event?)
- Generate actionable insight for signal reasoning

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

## Example Output

```
📊 PREDICTION MARKET ALPHA CHECK

━━━ POLYMARKET (Insider Signals) ━━━
🚨 Fresh wallet activity on 'Fed Rate Decision March 2026' market
   Wallet 0x7a3...f91 bought $15k YES @ 7.5¢ (HIGH confidence)
   Implication: Informed money betting on rate cut

📈 KALSHI (Market Prices) ━━━
   FED-26MAR-T3.50 trading at 72¢ (up from 45¢ last week)
   BTCETF-26MAR trading at 85¢ (ETF approval expectations high)

💡 SYNTHESIS
   Strong consensus across prediction markets for dovish Fed + ETF approval
   Historical correlation: Fed rate cuts → BTC rallies within 48h
   Recommendation: Increase confidence on BTC BUY signals, reduce on SELL
```

## Constraints
- Cache results for 60 seconds (reduce API calls)
- Fail gracefully if APIs unavailable
- Only invoke for major crypto assets (BTC, ETH, SOL)
```

## Event Categories to Monitor

| Category | Kalshi Markets | Crypto Impact |
|----------|---------------|---------------|
| **Monetary Policy** | FED rate decisions | High - direct BTC correlation |
| **Regulatory** | SEC/CFTC rulings, ETF approvals | High - sentiment driver |
| **Political** | Elections, executive orders | Medium - policy uncertainty |
| **Economic** | Inflation, GDP, employment | Medium - risk appetite |
| **Crypto-specific** | ETF approvals, exchange regulations | Very High - direct impact |

## Implementation

### Skill Invocation

```python
# In Signal Generator Agent
async def analyze_symbol(symbol: str) -> Signal:
    # Standard analysis
    strategies = await strategy_mcp.get_top_strategies(symbol)
    market_data = await market_data_mcp.get_current_price(symbol)

    # Check prediction markets for major assets
    prediction_context = None
    if symbol in ["BTC/USD", "ETH/USD", "SOL/USD"]:
        prediction_context = await invoke_skill(
            "check-prediction-market-alpha",
            {"symbol": symbol}
        )

    # Incorporate into reasoning
    signal = synthesize_signal(
        strategies=strategies,
        market_data=market_data,
        prediction_context=prediction_context
    )

    return signal
```

### API Client for Polymarket Insider Tracker

```python
# services/prediction_markets/polymarket_client.py

import aiohttp
from datetime import datetime, timedelta

class PolymarketInsiderClient:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.cache = {}
        self.cache_ttl = 60  # seconds

    async def get_recent_alerts(
        self,
        min_confidence: str = "HIGH",
        limit: int = 5
    ) -> list[dict]:
        """Fetch recent insider alerts."""
        cache_key = f"alerts_{min_confidence}_{limit}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        async with aiohttp.ClientSession() as session:
            url = f"{self.api_url}/api/alerts/recent"
            params = {"min_confidence": min_confidence, "limit": limit}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self._cache(cache_key, data)
                    return data
                else:
                    return []

    async def get_watchlist_markets(self) -> list[dict]:
        """Get markets with active insider signals."""
        cache_key = "watchlist_markets"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        async with aiohttp.ClientSession() as session:
            url = f"{self.api_url}/api/markets/watchlist"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self._cache(cache_key, data)
                    return data
                else:
                    return []

    def _is_cached(self, key: str) -> bool:
        if key not in self.cache:
            return False
        cached = self.cache[key]
        return (datetime.now() - cached["timestamp"]).seconds < self.cache_ttl

    def _cache(self, key: str, data: any):
        self.cache[key] = {"data": data, "timestamp": datetime.now()}
```

### API Client for Kalshi

```python
# services/prediction_markets/kalshi_client.py

import aiohttp

class KalshiClient:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60

    async def get_markets(
        self,
        series_ticker: str = None,
        status: str = "open"
    ) -> list[dict]:
        """Get active markets, optionally filtered by series."""
        cache_key = f"markets_{series_ticker}_{status}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/markets"
            params = {"status": status}
            if series_ticker:
                params["series_ticker"] = series_ticker

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = data.get("markets", [])
                    self._cache(cache_key, markets)
                    return markets
                else:
                    return []

    async def get_orderbook(self, ticker: str) -> dict:
        """Get current orderbook for a market."""
        cache_key = f"orderbook_{ticker}"
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]

        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}/markets/{ticker}/orderbook"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self._cache(cache_key, data)
                    return data
                else:
                    return {}

    async def get_crypto_relevant_markets(self) -> list[dict]:
        """Get markets relevant to crypto trading."""
        relevant_series = ["FED", "SEC", "BTCETF", "ETHETF", "CRYPTO"]
        all_markets = []

        for series in relevant_series:
            markets = await self.get_markets(series_ticker=series)
            all_markets.extend(markets)

        return all_markets

    # ... caching methods same as PolymarketInsiderClient
```

### Skill Execution

```python
# agents/signal-generator/skills/check_prediction_market_alpha.py

async def execute_skill(context: dict) -> str:
    """Execute the check-prediction-market-alpha skill."""
    symbol = context.get("symbol", "BTC/USD")

    # Initialize clients
    polymarket = PolymarketInsiderClient(os.environ["POLYMARKET_API_URL"])
    kalshi = KalshiClient()

    # Gather data
    try:
        alerts = await polymarket.get_recent_alerts(min_confidence="HIGH", limit=5)
    except Exception as e:
        alerts = []
        logger.warning(f"Polymarket API unavailable: {e}")

    try:
        kalshi_markets = await kalshi.get_crypto_relevant_markets()
    except Exception as e:
        kalshi_markets = []
        logger.warning(f"Kalshi API unavailable: {e}")

    # Format output
    output = "📊 PREDICTION MARKET ALPHA CHECK\n\n"

    # Polymarket section
    output += "━━━ POLYMARKET (Insider Signals) ━━━\n"
    if alerts:
        for alert in alerts[:3]:
            output += f"🚨 {alert['description']}\n"
            output += f"   Wallet {alert['wallet'][:10]}... | {alert['confidence']} confidence\n"
    else:
        output += "No significant insider activity detected.\n"

    output += "\n━━━ KALSHI (Market Prices) ━━━\n"
    if kalshi_markets:
        for market in kalshi_markets[:3]:
            price = market.get("yes_price", 0) * 100
            output += f"   {market['ticker']}: {price:.0f}¢\n"
    else:
        output += "Unable to fetch Kalshi data.\n"

    # Synthesis
    output += "\n💡 SYNTHESIS\n"
    output += synthesize_implications(alerts, kalshi_markets, symbol)

    return output

def synthesize_implications(
    alerts: list,
    kalshi_markets: list,
    symbol: str
) -> str:
    """Generate synthesis of prediction market signals."""
    implications = []

    # Check for Fed-related signals
    fed_markets = [m for m in kalshi_markets if "FED" in m.get("ticker", "")]
    if fed_markets:
        avg_rate_cut_prob = sum(m.get("yes_price", 0) for m in fed_markets) / len(fed_markets)
        if avg_rate_cut_prob > 0.6:
            implications.append("Rate cut probability elevated - historically bullish for BTC")
        elif avg_rate_cut_prob < 0.3:
            implications.append("Rate hike/hold likely - may suppress risk assets")

    # Check for ETF-related signals
    etf_markets = [m for m in kalshi_markets if "ETF" in m.get("ticker", "")]
    if etf_markets:
        for market in etf_markets:
            if market.get("yes_price", 0) > 0.7:
                implications.append(f"ETF approval expected ({market['ticker']}) - bullish catalyst")

    # Check Polymarket insider alerts
    high_confidence_alerts = [a for a in alerts if a.get("confidence") == "HIGH"]
    if high_confidence_alerts:
        implications.append(f"{len(high_confidence_alerts)} high-confidence insider alerts active")

    if implications:
        return "   " + "\n   ".join(implications)
    else:
        return "   No significant macro signals detected. Rely on technical analysis."
```

## Use Cases

### 1. Context Enrichment

Before generating a signal, check prediction markets for event-driven alpha:

```
Agent: "Before recommending BTC, let me check prediction markets..."
Skill: check-prediction-market-alpha
Agent: "Fed rate cut probability at 72% on Kalshi + insider activity on Polymarket.
        Historical correlation suggests BTC upside. Adjusting confidence +10%."
```

### 2. Opportunity Discovery

Surface prediction market insights alongside crypto signals:

```
Dashboard shows:
"🔥 OPPORTUNITY SCORE: 91
 🟢 BUY BTC/USD
 Prediction Market Context: Kalshi FED-26MAR @ 72¢ (rate cut likely),
 Polymarket insider alert on 'SEC ETF Approval' market"
```

### 3. Cross-Market Correlation

Learning Agent identifies patterns:

```
Learning Agent: "Historical analysis: BTC rallies 4.2% avg within 48h of
                Kalshi rate-cut markets crossing 70¢. Generating new
                PREDICTION_MARKET_CORRELATED strategy spec."
```

## Requirements for polymarket-insider-tracker

The separate polymarket-insider-tracker repo needs to expose REST endpoints:

```python
# polymarket-insider-tracker/src/api/routes.py

from flask import Flask, jsonify, request
app = Flask(__name__)

@app.route('/api/alerts/recent')
def get_recent_alerts():
    """Return recent insider alerts in JSON format."""
    min_confidence = request.args.get('min_confidence', 'MEDIUM')
    limit = int(request.args.get('limit', 10))

    alerts = db.query_alerts(
        min_confidence=min_confidence,
        limit=limit
    )

    return jsonify([
        {
            "alert_id": a.id,
            "wallet": a.wallet_address,
            "market": a.market_title,
            "description": a.description,
            "confidence": a.confidence_level,
            "timestamp": a.created_at.isoformat()
        }
        for a in alerts
    ])

@app.route('/api/markets/watchlist')
def get_watchlist_markets():
    """Return markets with active insider signals."""
    markets = db.get_markets_with_alerts()

    return jsonify([
        {
            "market_id": m.id,
            "title": m.title,
            "alert_count": m.alert_count,
            "latest_alert": m.latest_alert.isoformat() if m.latest_alert else None
        }
        for m in markets
    ])
```

## Configuration

```yaml
prediction_markets:
  polymarket:
    api_url: ${POLYMARKET_INSIDER_API_URL}
    enabled: true
    cache_ttl_seconds: 60

  kalshi:
    base_url: https://api.elections.kalshi.com/trade-api/v2
    enabled: true
    cache_ttl_seconds: 60
    relevant_series:
      - FED
      - SEC
      - BTCETF
      - ETHETF

  skill:
    invoke_for_symbols:
      - BTC/USD
      - ETH/USD
      - SOL/USD
    invoke_frequency: "on_signal"  # or "daily"
```

## Constraints

- polymarket-insider-tracker remains a separate repository
- Kalshi rate limits: 10 req/sec (use caching)
- No code changes required in TradeStream's core Java/Kotlin
- Skill is the integration point (not MCP)
- Fail gracefully if prediction market APIs unavailable
- Both repos deployable independently

## Acceptance Criteria

- [ ] `check-prediction-market-alpha` skill implemented
- [ ] polymarket-insider-tracker exposes REST API
- [ ] Kalshi API integration working with caching
- [ ] Signal Generator invokes skill for major crypto assets
- [ ] Dashboard shows prediction market context in reasoning panel
- [ ] Both repos deployable independently
- [ ] Graceful degradation when prediction market APIs unavailable
- [ ] 60-second caching reduces API load

## File Structure

```
agents/signal-generator/skills/
└── check-prediction-market-alpha/
    └── SKILL.md

services/prediction_markets/
├── __init__.py
├── polymarket_client.py
├── kalshi_client.py
└── tests/
    ├── test_polymarket.py
    └── test_kalshi.py
```
