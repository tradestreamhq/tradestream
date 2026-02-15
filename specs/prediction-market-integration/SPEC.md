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
+---------------------------------------------------------------------+
|  TRADESTREAM AGENTS                                                 |
|                                                                     |
|  Signal Generator Agent                                             |
|       |                                                             |
|       +---> strategy-mcp (internal)                                 |
|       +---> market-data-mcp (internal)                              |
|       +---> SKILL: check-prediction-market-alpha                    |
|                    |                                                |
+--------------------+------------------------------------------------+
                     |
           +---------+---------+
           v                   v
+--------------------+  +--------------------+
|  POLYMARKET        |  |  KALSHI            |
|  INSIDER TRACKER   |  |  API               |
|  (separate repo)   |  |  (kalshi.com/api)  |
|  [OPTIONAL]        |  |  [OPTIONAL]        |
|                    |  |                    |
|  /api/alerts/...   |  |  /markets/...      |
|  /api/wallets/...  |  |  /events/...       |
+--------------------+  +--------------------+
```

## Prediction Market Sources

### Polymarket (via polymarket-insider-tracker) - OPTIONAL

| Endpoint                 | Purpose                      | Data                               |
| ------------------------ | ---------------------------- | ---------------------------------- |
| `/api/alerts/recent`     | Suspicious wallet activity   | Wallet, market, confidence, timing |
| `/api/wallets/watchlist` | Known insider wallets        | Wallet addresses, history          |
| `/api/markets/watchlist` | Markets with insider signals | Market IDs, alert counts           |

**Note**: Polymarket integration is optional. The skill operates in degraded mode if polymarket-insider-tracker is unavailable.

### Kalshi (Official API) - OPTIONAL

| Endpoint                          | Purpose                 | Data                     |
| --------------------------------- | ----------------------- | ------------------------ |
| `GET /markets`                    | List active markets     | Tickers, prices, volume  |
| `GET /markets/{ticker}/orderbook` | Current prices + volume | Bid/ask, depth           |
| `GET /events/{event_ticker}`      | Event details           | Series, settlement dates |

**Note**: Kalshi integration is optional. The skill operates in degraded mode if Kalshi API is unavailable.

## Why Skill > MCP for This Use Case

| Aspect                | MCP Tool                | Skill                          |
| --------------------- | ----------------------- | ------------------------------ |
| **Abstraction Level** | Low (single API call)   | High (workflow with reasoning) |
| **Context**           | None                    | Full conversation context      |
| **Output**            | Raw JSON                | Interpreted analysis           |
| **Best For**          | Frequent atomic queries | Complex multi-step analysis    |

For prediction markets, we want:

- Contextual reasoning about _why_ alerts matter for crypto
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

### 1. Polymarket (Insider Signals) - Optional

Fetch recent high-confidence insider alerts from polymarket-insider-tracker API:

- Look for fresh wallet activity, unusual sizing, niche market entries
- Cross-reference alert categories with current trading symbols
- If unavailable, use cached data or skip this source

### 2. Kalshi (Market Movements) - Optional

Check crypto-relevant markets:

- Fed rate decisions (FED-\*)
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

## Example Output

### Full Mode (Both Sources Available)

```

PREDICTION MARKET ALPHA CHECK

--- DATA FRESHNESS ---
Polymarket: LIVE (fetched 3s ago)
Kalshi: LIVE (fetched 5s ago)

--- POLYMARKET (Insider Signals) ---
[!] Fresh wallet activity on 'Fed Rate Decision March 2026' market
Wallet 0x7a3...f91 bought $15k YES @ 7.5c (HIGH confidence)
Implication: Informed money betting on rate cut

--- KALSHI (Market Prices) ---
FED-26MAR-T3.50 trading at 72c (up from 45c last week)
BTCETF-26MAR trading at 85c (ETF approval expectations high)

[*] SYNTHESIS
Strong consensus across prediction markets for dovish Fed + ETF approval
Historical correlation: Fed rate cuts -> BTC rallies within 48h
Recommendation: Increase confidence on BTC BUY signals, reduce on SELL

```

### Degraded Mode (Polymarket Unavailable)

```

PREDICTION MARKET ALPHA CHECK

--- DATA FRESHNESS ---
Polymarket: UNAVAILABLE (using cached data from 2m ago)
Kalshi: LIVE (fetched 3s ago)

--- POLYMARKET (Insider Signals) ---
[CACHED] Last known insider activity from 2m ago:
Wallet 0x7a3...f91 activity on Fed market (data may be stale)

--- KALSHI (Market Prices) ---
FED-26MAR-T3.50 trading at 72c
BTCETF-26MAR trading at 85c

[*] SYNTHESIS
Kalshi data available; Polymarket data stale.
Fed rate cut probability elevated. Limited insider signal confidence.

```

### Fallback Mode (Both Sources Unavailable)

```

PREDICTION MARKET ALPHA CHECK

[!!] DATA UNAVAILABLE
All prediction market sources are currently unreachable.

[*] RECOMMENDATION
Rely on technical analysis and on-chain data for BTC/USD.
No event-driven alpha signals available at this time.

Data freshness: N/A (no data)
Sources checked: Polymarket (down), Kalshi (down)

```

## Constraints
- Cache results using configurable TTL (default 60 seconds, reduce for fast-moving events)
- Polymarket is optional - skill operates in degraded mode if unavailable
- Kalshi is optional - skill operates in degraded mode if unavailable
- Fail gracefully with baseline response if both sources unavailable
- Only invoke for major crypto assets (BTC, ETH, SOL)
```

## Event Categories to Monitor

| Category            | Kalshi Markets                      | Crypto Impact                 |
| ------------------- | ----------------------------------- | ----------------------------- |
| **Monetary Policy** | FED rate decisions                  | High - direct BTC correlation |
| **Regulatory**      | SEC/CFTC rulings, ETF approvals     | High - sentiment driver       |
| **Political**       | Elections, executive orders         | Medium - policy uncertainty   |
| **Economic**        | Inflation, GDP, employment          | Medium - risk appetite        |
| **Crypto-specific** | ETF approvals, exchange regulations | Very High - direct impact     |

## Source Availability and Fallback Behavior

Prediction market sources are **optional dependencies**. The skill operates in degraded modes when sources are unavailable:

### Availability Modes

| Mode                | Polymarket  | Kalshi      | Behavior                                |
| ------------------- | ----------- | ----------- | --------------------------------------- |
| **Full**            | Available   | Available   | Complete analysis with both sources     |
| **Kalshi-only**     | Unavailable | Available   | Market prices only, no insider signals  |
| **Polymarket-only** | Available   | Unavailable | Insider signals only, no market prices  |
| **Degraded**        | Unavailable | Unavailable | Return cached data or baseline response |

### Fallback Strategy

1. **Primary**: Fetch live data from each enabled source
2. **Secondary**: If live fetch fails, use stale cache (up to 5 minutes old)
3. **Tertiary**: If no cache available, operate without that source
4. **Baseline**: If all sources unavailable with no cache, return baseline response

## A/B Testing Framework

To validate the alpha contribution of prediction market signals, implement A/B testing:

### Experiment Design

```yaml
ab_test:
  name: "prediction_market_alpha_v1"
  description: "Measure alpha contribution from prediction market signals"

  control_group:
    name: "no_prediction_markets"
    behavior: "Generate signals using technical analysis only"
    allocation: 50%

  treatment_group:
    name: "with_prediction_markets"
    behavior: "Generate signals with prediction market context"
    allocation: 50%

  metrics:
    primary:
      - name: "signal_accuracy"
        definition: "Percentage of signals that moved in predicted direction within 24h"
      - name: "alpha_bps"
        definition: "Excess return in basis points vs control"
    secondary:
      - name: "confidence_calibration"
        definition: "Correlation between signal confidence and actual accuracy"
      - name: "event_timing_accuracy"
        definition: "Accuracy of event-driven signals around Fed/ETF announcements"

  duration: "30 days minimum"
  sample_size: "1000 signals per group minimum"

  success_criteria:
    - "signal_accuracy improvement >= 5% with p-value < 0.05"
    - "alpha_bps >= 50 with p-value < 0.05"
```

## Configuration

```yaml
prediction_markets:
  polymarket:
    api_url: ${POLYMARKET_INSIDER_API_URL}
    enabled: true # Set to false to disable Polymarket integration
    cache_ttl_seconds: 60 # Configurable: reduce for fast-moving events (e.g., 15-30s during Fed meetings)
    stale_cache_max_age_seconds: 300 # Max age for fallback cache
    timeout_seconds: 5.0

  kalshi:
    base_url: https://api.elections.kalshi.com/trade-api/v2
    enabled: true # Set to false to disable Kalshi integration
    cache_ttl_seconds: 60 # Configurable: reduce for fast-moving events
    stale_cache_max_age_seconds: 300
    timeout_seconds: 5.0
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
    invoke_frequency: "on_signal" # or "daily"

  ab_testing:
    enabled: true
    experiment_name: "prediction_market_alpha_v1"
    control_allocation: 0.5 # 50% control, 50% treatment
```

## Constraints

- polymarket-insider-tracker remains a separate repository
- Kalshi rate limits: 10 req/sec (use caching)
- No code changes required in TradeStream's core Java/Kotlin
- Skill is the integration point (not MCP)
- Polymarket integration is **optional** - system operates without it
- Kalshi integration is **optional** - system operates without it
- Both repos deployable independently

## Acceptance Criteria

- [ ] `check-prediction-market-alpha` skill implemented
- [ ] polymarket-insider-tracker exposes REST API
- [ ] Kalshi API integration working with caching
- [ ] Signal Generator invokes skill for major crypto assets
- [ ] Dashboard shows prediction market context in reasoning panel
- [ ] Both repos deployable independently
- [ ] Graceful degradation when Polymarket unavailable (Kalshi-only mode)
- [ ] Graceful degradation when Kalshi unavailable (Polymarket-only mode)
- [ ] Baseline response when both sources unavailable
- [ ] Configurable cache TTL per data source
- [ ] Data freshness indicators in skill output
- [ ] A/B testing framework deployed to measure alpha contribution

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

services/ab_testing/
├── __init__.py
├── prediction_market_experiment.py
└── tests/
    └── test_experiment.py
```
