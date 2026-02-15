# External Signal Sources

## Goal

Augment TradeStream's technical-analysis-only signal engine with external data sources — social media sentiment, financial news, influential trader calls, whale wallet movements, and market sentiment indices — to produce higher-quality, multi-dimensional trading signals that reflect both price action and the broader market narrative.

## Target Behavior

External signal data flows through dedicated ingestion pipelines into a unified **External Signals Score** (0-1) that plugs into the opportunity scoring formula as a single composite factor. Each sub-source contributes a normalized score; the External Signals Score aggregates them with configurable weights. When external data is unavailable, the system degrades gracefully to TA-only scoring.

### Why This Matters

TradeStream currently scores opportunities using 5 purely technical factors (confidence, expected return, consensus, volatility, freshness). This misses:

- **Narrative shifts** that move markets before technicals confirm (social sentiment, news)
- **Smart money positioning** visible on-chain but invisible in price data (whale movements)
- **Crowd psychology extremes** that signal contrarian opportunities (Fear & Greed, funding rates)
- **Influencer-driven momentum** that triggers retail flows (CT/KOL calls)

Adding external signals transforms TradeStream from "what does price say?" to "what does the entire market ecosystem say?" — a significant competitive moat.

## Architecture Overview

```
                    EXTERNAL SIGNALS ARCHITECTURE

  DATA SOURCES
  +-----------+  +-----------+  +-----------+  +-----------+  +-----------+
  | Twitter/X |  | CoinDesk  |  | Crypto    |  | Blockchain|  | Fear &    |
  | Reddit    |  | The Block |  | Twitter   |  | RPCs      |  | Greed     |
  | Telegram  |  | Reuters   |  | YouTube   |  | Whale     |  | Funding   |
  | Discord   |  | SEC/CFTC  |  | Telegram  |  | Alert     |  | Rates     |
  |           |  |           |  | Groups    |  | Nansen    |  | OI/LS     |
  +-----+-----+  +-----+-----+  +-----+-----+  +-----+-----+  +-----+-----+
        |              |              |              |              |
        v              v              v              v              v
  +-----------+  +-----------+  +-----------+  +-----------+  +-----------+
  | Social    |  | News      |  | Influencer|  | Whale     |  | Sentiment |
  | Sentiment |  | Analysis  |  | Tracking  |  | Monitoring|  | Indices   |
  | Pipeline  |  | Pipeline  |  | Pipeline  |  | Pipeline  |  | Pipeline  |
  +-----------+  +-----------+  +-----------+  +-----------+  +-----------+
        |              |              |              |              |
        v              v              v              v              v
  Kafka Topic:   Kafka Topic:   Kafka Topic:   Kafka Topic:   Kafka Topic:
  social.scores  news.scores    influencer.    whale.scores   sentiment.
                                scores                        scores
        |              |              |              |              |
        +-------+------+------+------+------+-------+              |
                |                                                  |
                v                                                  v
  +-----------------------------------+          +------------------+
  |   EXTERNAL SIGNALS AGGREGATOR     |          | Market Regime    |
  |                                   |          | Enhancer         |
  |   - Weighted combination          |          | (sentiment +     |
  |   - Missing data fallback         |          |  volatility)     |
  |   - Contrarian adjustments        |          +--------+---------+
  |   - Conflict detection            |                   |
  +----------------+------------------+                   |
                   |                                      |
                   v                                      v
  +-----------------------------------------------------------+
  |              OPPORTUNITY SCORER                             |
  |                                                             |
  |  Existing TA Factors (85%)   +   External Signals (15%)    |
  +-----------------------------------------------------------+
                   |
                   v
  +-----------------------------------------------------------+
  |          Kafka: scored-signals                              |
  +-----------------------------------------------------------+
```

## Sub-Specifications

| Spec | Purpose | Score Output | Priority | Est. Cost |
|------|---------|-------------|----------|-----------|
| [social-sentiment](./social-sentiment/SPEC.md) | Twitter/X, Reddit, Telegram NLP sentiment | `social_sentiment_score` (0-1) | P1 | $200-500/mo |
| [news-analysis](./news-analysis/SPEC.md) | Financial news event extraction & impact scoring | `news_impact_score` (0-1) | P1 | $300-800/mo |
| [influencer-tracking](./influencer-tracking/SPEC.md) | Track external crypto influencer calls & accuracy | `influencer_consensus_score` (0-1) | P2 | ~$115/mo |
| [whale-monitoring](./whale-monitoring/SPEC.md) | On-chain whale wallet movement detection | `whale_activity_score` (0-1) | P2 | $356-3,096/mo |
| [sentiment-indices](./sentiment-indices/SPEC.md) | Fear & Greed, funding rates, OI, stablecoin flows | `market_sentiment_score` (0-1) | P1 | $100-400/mo |

## Unified External Signals Score

Each sub-source produces an independent 0-1 score. The **External Signals Aggregator** combines them into a single `external_signals_score` (0-1):

### Aggregation Weights

| Sub-Source | Weight | Rationale |
|------------|--------|-----------|
| Market Sentiment Indices | 30% | Highest predictive power (funding rates, OI), most frequent updates |
| News Impact | 25% | Market-moving events have immediate, measurable price impact |
| Social Sentiment | 20% | Crowd narrative drives retail flows, but noisy |
| Whale Activity | 15% | Smart money signal, but sparse and harder to interpret |
| Influencer Consensus | 10% | Supplementary; reliability varies, smaller signal |

### Aggregation Formula

```python
def calculate_external_signals_score(
    social_sentiment: float | None,       # 0-1
    news_impact: float | None,            # 0-1
    influencer_consensus: float | None,   # 0-1
    whale_activity: float | None,         # 0-1
    market_sentiment: float | None,       # 0-1
) -> float:
    """
    Aggregate sub-source scores into unified external signals score.
    Handles missing data by redistributing weights proportionally.

    Returns:
        Float between 0.0 and 1.0
    """
    sources = {
        "market_sentiment": (market_sentiment, 0.30),
        "news_impact": (news_impact, 0.25),
        "social_sentiment": (social_sentiment, 0.20),
        "whale_activity": (whale_activity, 0.15),
        "influencer_consensus": (influencer_consensus, 0.10),
    }

    # Filter to available sources
    available = {k: (score, weight) for k, (score, weight) in sources.items() if score is not None}

    if not available:
        return 0.5  # Neutral fallback when no external data available

    # Redistribute weights proportionally among available sources
    total_available_weight = sum(w for _, w in available.values())
    score = sum(
        s * (w / total_available_weight)
        for s, w in available.values()
    )

    return round(max(0.0, min(1.0, score)), 4)
```

### Missing Data Handling

| Scenario | Behavior |
|----------|----------|
| All 5 sources available | Normal weighted aggregation |
| 1-4 sources missing | Redistribute weight proportionally to available sources |
| All sources missing | Return 0.5 (neutral), opportunity score uses TA factors only |
| Source stale (>2x expected refresh) | Apply staleness penalty (score decays toward 0.5) |

## Integration with Opportunity Scoring

### Updated Weight Distribution

The `external_signals_score` becomes the 6th factor in opportunity scoring:

| Factor | Current Weight | New Weight | Change |
|--------|---------------|------------|--------|
| Confidence | 25% | 22% | -3% |
| Expected Return | 30% | 26% | -4% |
| Strategy Consensus | 20% | 17% | -3% |
| Volatility | 15% | 12% | -3% |
| Freshness | 10% | 8% | -2% |
| **External Signals** | — | **15%** | **+15%** |

### Updated Scoring Formula

```python
def calculate_opportunity_score(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    external_signals_score: float,     # NEW: 0.0 - 1.0
    market_regime: str = "normal",
) -> float:
    caps = get_regime_adjusted_caps(market_regime)

    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)
    volatility_score = min(volatility / caps.max_volatility, 1.0)
    freshness_score = max(0, 1 - (minutes_ago / 60))

    opportunity_score = (
        0.22 * confidence +
        0.26 * return_score +
        0.17 * consensus_pct +
        0.12 * volatility_score +
        0.08 * freshness_score +
        0.15 * external_signals_score   # NEW
    ) * 100

    return round(opportunity_score, 1)
```

### Signal Suppression and Amplification

External signals can override or adjust TA-based scores in extreme scenarios:

| Condition | Action | Magnitude |
|-----------|--------|-----------|
| Breaking news: major hack/exploit | Suppress BUY signals for affected symbol | -20 pts |
| Whale exchange inflow > 5% daily volume | Suppress BUY signals | -15 pts |
| Extreme Fear + TA BUY consensus | Contrarian bonus | +10 pts |
| Extreme Greed + TA SELL consensus | Contrarian bonus | +8 pts |
| 3+ high-reliability influencers agree with TA | Confirmation bonus | +10 pts |
| Influencer consensus conflicts with TA | Conflict penalty | -5 pts |

### Score Breakdown Display (Updated)

```
OPPORTUNITY SCORE: 91

Confidence         82%    ████████░░    +18.0 pts
Expected Return    +3.2%  ██████████    +26.0 pts  (risk-adjusted)
Strategy Consensus 80%    ████████░░    +13.6 pts
Volatility         2.1%   ███████░░░    + 8.4 pts  (regime: normal)
Freshness          0m     ██████████    + 8.0 pts  (cached)
External Signals   0.78   ████████░░    +11.7 pts  (NEW)
  ├─ Sentiment Indices:  0.72  (Fear & Greed: 35, Funding: -0.02%)
  ├─ News Impact:        0.85  (Breaking: ETH ETF inflows surge)
  ├─ Social Sentiment:   0.81  (Twitter volume 3.2x avg, bullish)
  ├─ Whale Activity:     0.68  (Exchange outflows +12%)
  └─ Influencer:         0.90  (3/4 top KOLs bullish)
                         ─────────────────────
                         Total: 91.0 pts  (+5.7 from external)
```

## Enhanced Market Regime Detection

External data improves market regime classification beyond pure volatility:

| Regime | Volatility | Sentiment | Description | Cap Adjustment |
|--------|-----------|-----------|-------------|----------------|
| Normal | < 80th pct | 30-70 | Typical conditions | Standard caps |
| High Volatility | >= 80th pct | Any | Elevated vol | 1.7x caps |
| Capitulation | >= 80th pct | < 20 (Extreme Fear) | Panic selling, potential bottom | 2x caps, contrarian BUY bonus |
| Blow-off Top | >= 80th pct | > 80 (Extreme Greed) | Euphoria, potential top | 2x caps, contrarian SELL bonus |
| Accumulation | < 80th pct | < 30 | Quiet fear, smart money buying | Standard caps, whale weight +50% |
| Distribution | < 80th pct | > 70 | Quiet greed, smart money selling | Standard caps, whale weight +50% |

## Phased Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4) — P1 Sources

**Goal**: Get external data flowing into opportunity scoring with minimal complexity.

| Week | Deliverable | Source |
|------|------------|--------|
| 1-2 | Sentiment indices pipeline (Fear & Greed, funding rates, OI) | sentiment-indices |
| 2-3 | News ingestion via RSS + basic event classification | news-analysis |
| 3-4 | LunarCrush integration for social sentiment (MVP) | social-sentiment |
| 4 | External Signals Aggregator + updated opportunity scoring | this spec |

**Milestone**: Opportunity scores reflect 3 external factors. Dashboard shows external signal breakdown.

### Phase 2: Depth (Weeks 5-8) — Add On-Chain & Influencers

| Week | Deliverable | Source |
|------|------------|--------|
| 5-6 | Whale monitoring via Whale Alert API + exchange flow detection | whale-monitoring |
| 6-7 | Influencer registry + call detection NLP | influencer-tracking |
| 7-8 | Direct Twitter/Reddit API integration (replace LunarCrush for social) | social-sentiment |
| 8 | Contrarian signal logic + enhanced market regime detection | this spec |

**Milestone**: All 5 external sources active. Contrarian signals firing. Smart regime detection.

### Phase 3: Intelligence (Weeks 9-12) — Validation & Optimization

| Week | Deliverable | Source |
|------|------------|--------|
| 9-10 | Historical backtesting: correlate external signals with price outcomes | all specs |
| 10-11 | Weight optimization based on backtesting results | this spec |
| 11-12 | Anti-gaming for influencer tracking, bot filtering for social | influencer/social |
| 12 | Breaking news detection (multi-source dedup + alert) | news-analysis |

**Milestone**: Weights validated against historical data. Anti-abuse active. Full production readiness.

### Phase 4: Scale (Weeks 13+) — Advanced Features

- Direct blockchain RPC monitoring (Nansen/Arkham integration)
- Telegram channel scraping + Discord bot for social sentiment
- LLM-based news summarization in signal reasoning
- User-configurable external signal weights
- External signals as standalone alert channel (e.g., "whale alert" notifications)

## Cost Analysis

### Monthly Infrastructure Cost Estimates

| Source | MVP (Phase 1) | Production (Phase 2+) | Notes |
|--------|--------------|----------------------|-------|
| Social Sentiment | $200-500 | $500-1,200 | LunarCrush MVP → direct APIs |
| News Analysis | $0-300 | $300-800 | RSS free, premium APIs paid |
| Influencer Tracking | $0 | ~$115 | Public API access, LLM costs |
| Whale Monitoring | $0-100 | $356-3,096 | Free tier → production analytics |
| Sentiment Indices | $0-100 | $100-400 | Fear & Greed free, premium APIs |
| **Total** | **$200-1,000** | **$1,371-5,611** | |

### Cost Optimization Strategy

1. **Start with free/cheap sources**: Fear & Greed (free), RSS feeds (free), LunarCrush ($200/mo)
2. **Validate before scaling**: Only upgrade to premium data after backtesting confirms value
3. **Cache aggressively**: Most sentiment data changes slowly; 5-15 min cache is fine
4. **Share API calls**: Social sentiment and influencer tracking share Twitter/Reddit API access

## Competitive Positioning

With external signals, TradeStream's positioning evolves:

| Before | After |
|--------|-------|
| "Signals backed by strategy consensus" | "Signals backed by strategy consensus **and market intelligence**" |
| TA-only, 60+ indicators | TA + sentiment + news + on-chain + influencer data |
| Reacts to price | Reacts to price **and narrative** |
| Single dimension (technical) | Multi-dimensional (technical + social + on-chain) |

### Competitive Comparison (Updated)

```
+-----------------------------------------+-------------+-----------+--------------+
| Feature                                 | TradeStream | moomoo    | Generic Bots |
+-----------------------------------------+-------------+-----------+--------------+
| Strategy Library                        | 40M+        | -         | -            |
| Genetic Discovery                       | Yes         | -         | -            |
| Opportunity Scoring                     | Yes         | -         | -            |
| Strategy Transparency                   | Yes         | -         | -            |
| Forward-Test Validation                 | Yes         | -         | -            |
| Social Sentiment Analysis               | Yes (NEW)   | Basic     | -            |
| News Impact Scoring                     | Yes (NEW)   | Basic     | -            |
| Whale Movement Tracking                 | Yes (NEW)   | -         | -            |
| Influencer Call Tracking                | Yes (NEW)   | -         | -            |
| Market Sentiment Indices                | Yes (NEW)   | Basic     | -            |
| Multi-Channel Alerts                    | Yes         | Yes       | Limited      |
+-----------------------------------------+-------------+-----------+--------------+
```

## Kafka Topic Design

| Topic | Key | Value | Retention |
|-------|-----|-------|-----------|
| `external.social.scores` | symbol | SocialSentimentScore proto | 7 days |
| `external.news.events` | symbol | NewsEvent proto | 30 days |
| `external.news.scores` | symbol | NewsImpactScore proto | 7 days |
| `external.influencer.calls` | symbol | InfluencerCall proto | 30 days |
| `external.influencer.scores` | symbol | InfluencerConsensusScore proto | 7 days |
| `external.whale.movements` | symbol | WhaleMovement proto | 30 days |
| `external.whale.scores` | symbol | WhaleActivityScore proto | 7 days |
| `external.sentiment.scores` | symbol | MarketSentimentScore proto | 7 days |
| `external.aggregated` | symbol | ExternalSignalsScore proto | 7 days |

## Configuration

```yaml
external_signals:
  enabled: true

  # Aggregation weights for composite score
  aggregation_weights:
    market_sentiment: 0.30
    news_impact: 0.25
    social_sentiment: 0.20
    whale_activity: 0.15
    influencer_consensus: 0.10

  # Opportunity scoring integration
  opportunity_scoring_weight: 0.15  # 15% of total opportunity score

  # Missing data behavior
  missing_data:
    fallback_score: 0.5             # Neutral when all sources missing
    staleness_penalty_factor: 0.1   # Score decays 10% per staleness interval
    min_sources_for_confidence: 2   # Need 2+ sources for full weight

  # Signal suppression/amplification
  overrides:
    breaking_news_suppression: -20  # Points deducted for major negative news
    whale_inflow_suppression: -15   # Points deducted for large exchange inflows
    contrarian_fear_bonus: 10       # Points added for extreme fear + TA BUY
    contrarian_greed_bonus: 8       # Points added for extreme greed + TA SELL
    influencer_confirmation: 10     # Points added for influencer + TA agreement
    influencer_conflict: -5         # Points deducted for influencer vs TA conflict

  # Enhanced market regime detection
  regime_enhancement:
    enabled: true
    capitulation_threshold:         # Fear < 20 AND vol >= 80th pct
      fear_max: 20
      volatility_min_percentile: 0.80
    blowoff_top_threshold:          # Greed > 80 AND vol >= 80th pct
      greed_min: 80
      volatility_min_percentile: 0.80
```

## Constraints

- External signals must NEVER override TA consensus — they supplement, not replace
- Total external signal contribution capped at 15% of opportunity score (configurable)
- System must function at full capacity when all external sources are unavailable
- Individual source failures must not cascade (circuit breaker per source)
- All external data cached with TTL; stale data penalized but not immediately dropped
- Raw external data retained per source-specific retention policies (7-365 days)
- LLM/NLP costs must be monitored and capped per billing period
- External signal pipelines must not increase end-to-end signal latency by more than 5 seconds

## Non-Goals

- **Trade execution**: External signals inform scoring only, never trigger automatic trades
- **Proprietary data**: No paid insider info, private Telegram groups, or non-public data
- **User-generated signals**: Internal provider signals (viral-platform) are separate from external data
- **Replacing TA**: External data is supplementary; TA remains the primary signal source
- **Real-time chat**: No Telegram/Discord community management features (covered by viral-platform spec)

## Acceptance Criteria

- [ ] External Signals Aggregator produces `external_signals_score` (0-1) per symbol
- [ ] Opportunity scoring formula updated with 15% external signals weight
- [ ] Score breakdown in dashboard shows external signal components
- [ ] Missing external data handled gracefully (proportional weight redistribution)
- [ ] All external sources unavailable → scoring falls back to TA-only (no degradation)
- [ ] At least 3 external sources active in Phase 1 (sentiment indices, news, social)
- [ ] Breaking news events suppress conflicting TA signals within 60 seconds
- [ ] Contrarian signals fire at extreme sentiment levels
- [ ] Enhanced market regime detection uses sentiment + volatility matrix
- [ ] External signal latency adds < 5 seconds to end-to-end scoring
- [ ] Per-source circuit breakers prevent cascade failures
- [ ] Historical backtesting validates external signal predictive value
- [ ] Monthly cost stays within budget ($200-1,000 Phase 1, $1,400-5,600 Phase 2+)

## Implementing Issues

| Issue | Status | Description |
|-------|--------|-------------|
| #000  | open   | Implement External Signals Aggregator service |
| #000  | open   | Update opportunity scoring formula with external weight |
| #000  | open   | Add external signal breakdown to dashboard UI |
| #000  | open   | Implement circuit breakers for external data sources |
| #000  | open   | Backtest external signals against historical price data |

## Metrics

- `external_signals_score_distribution` — Histogram of aggregated scores
- `external_signals_source_availability` — Per-source uptime percentage
- `external_signals_staleness_seconds` — Age of latest data per source
- `external_signals_aggregation_latency_ms` — Time to compute aggregated score
- `external_signals_suppression_events_total` — Count of signal suppressions
- `external_signals_contrarian_events_total` — Count of contrarian signals
- `external_signals_monthly_cost_usd` — Tracked API/infra spend per source
- `external_signals_backtest_correlation` — Correlation of external score with forward returns

## Notes

### Weight Tuning Strategy

Initial weights (30/25/20/15/10) are based on theoretical signal quality and update frequency. After Phase 3 backtesting, weights should be optimized using:

1. **Correlation analysis**: Which sub-source correlates most with 1h/4h/24h forward returns?
2. **Information ratio**: Which source adds the most new information not already in TA signals?
3. **Granger causality**: Which source leads price movements vs. lags them?

Expect market sentiment indices (funding rates, OI) to remain highest-weighted, as they directly reflect leveraged positioning.

### Relationship to Existing Specs

- **opportunity-scoring**: This spec extends the scoring formula with a 6th factor
- **viral-platform/social-features**: Internal social layer (follows, reactions) is separate from external data ingestion
- **multi-channel-delivery**: External signal events can trigger delivery alerts (e.g., "whale alert" notifications)
- **differentiation**: External signals strengthen the competitive moat significantly
