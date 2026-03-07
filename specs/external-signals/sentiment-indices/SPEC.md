# Sentiment & Market Indices Integration

## Goal

Integrate external sentiment indices and market structure data as signal factors in the opportunity scoring pipeline, enabling TradeStream to combine technical analysis with crowd sentiment, on-chain metrics, and derivatives market positioning for higher-quality trading signals.

## Target Behavior

The system polls external sentiment and market structure data sources on configured intervals, normalizes each into a 0-1 scale, computes a composite sentiment score, and publishes it to Kafka for consumption by opportunity scoring and market regime detection. When sentiment reaches extreme levels, the system generates contrarian signals and adjusts market regime classification.

### Composite Sentiment Score

Every active symbol receives a continuously-updated `market_sentiment_score` (0.0-1.0) derived from three categories:

| Category | Weight | Update Frequency | Description |
|----------|--------|-------------------|-------------|
| Crowd Sentiment | 35% | 15 min - 24 hr | Fear & Greed, social dominance, search trends, mention velocity |
| Market Structure | 45% | 1 min - 5 min | Funding rates, open interest, long/short ratios, liquidations |
| On-Chain Flows | 20% | 5 min - 1 hr | Exchange reserves, stablecoin flows, BTC dominance |

**Rationale for weights**: Market structure data (funding rates, OI, liquidations) updates most frequently and has the strongest short-term predictive power for crypto markets. Crowd sentiment provides medium-term directional bias. On-chain flows are leading indicators but update slowly and are weighted accordingly.

### Architecture

```
+-------------------------------------------------------------------+
|                    SENTIMENT INDICES PIPELINE                      |
|                                                                   |
|  DATA SOURCE POLLERS (per-source intervals)                       |
|  +-------------+  +-------------+  +-------------+               |
|  | Fear & Greed|  | LunarCrush  |  | Funding     |               |
|  | (24h poll)  |  | (15m poll)  |  | Rates (1m)  |               |
|  +------+------+  +------+------+  +------+------+               |
|         |                |                |                       |
|  +------+------+  +------+------+  +------+------+               |
|  | Google      |  | Reddit/X    |  | Open        |               |
|  | Trends (6h) |  | Velocity    |  | Interest    |               |
|  +------+------+  | (15m poll)  |  | (1m poll)   |               |
|         |         +------+------+  +------+------+               |
|         |                |                |                       |
|  +------+------+  +------+------+  +------+------+               |
|  | Santiment   |  | CryptoQuant |  | Liquidation |               |
|  | (1h poll)   |  | (5m poll)   |  | Data (1m)   |               |
|  +------+------+  +------+------+  +------+------+               |
|         |                |                |                       |
|         +--------+-------+-------+--------+                       |
|                  |                                                 |
|                  v                                                 |
|  +-------------------------------+                                |
|  | NORMALIZATION LAYER           |                                |
|  | - Scale each index to 0-1    |                                |
|  | - Handle missing/stale data  |                                |
|  | - Apply per-source staleness |                                |
|  +-------------------------------+                                |
|                  |                                                 |
|                  v                                                 |
|  +-------------------------------+                                |
|  | COMPOSITE SCORING ENGINE      |                                |
|  | - Weighted aggregation        |                                |
|  | - Contrarian signal detection |                                |
|  | - Regime enhancement          |                                |
|  +-------------------------------+                                |
|                  |                                                 |
|         +--------+--------+                                       |
|         v                 v                                       |
|  +-------------+  +------------------+                            |
|  | Kafka Topic |  | InfluxDB         |                            |
|  | sentiment.  |  | (historical      |                            |
|  | scores      |  |  tracking)       |                            |
|  +------+------+  +------------------+                            |
|         |                                                         |
|    +----+----+                                                    |
|    v         v                                                    |
|  +--------+ +------------------+                                  |
|  | Oppty  | | Market Regime    |                                  |
|  | Scorer | | Detector         |                                  |
|  +--------+ +------------------+                                  |
+-------------------------------------------------------------------+
```

### Scored Sentiment Output Format

```json
{
  "symbol": "ETH/USD",
  "timestamp": "2026-02-15T12:34:56Z",
  "composite_score": 0.72,
  "category_scores": {
    "crowd_sentiment": {
      "score": 0.68,
      "weight": 0.35,
      "contribution": 0.238,
      "components": {
        "fear_greed_index": { "raw": 72, "normalized": 0.72, "age_minutes": 120, "stale": false },
        "social_dominance": { "raw": 4.2, "normalized": 0.56, "age_minutes": 10, "stale": false },
        "google_trends": { "raw": 65, "normalized": 0.65, "age_minutes": 180, "stale": false },
        "mention_velocity": { "raw": 1.8, "normalized": 0.80, "age_minutes": 8, "stale": false }
      }
    },
    "market_structure": {
      "score": 0.75,
      "weight": 0.45,
      "contribution": 0.3375,
      "components": {
        "funding_rate": { "raw": 0.015, "normalized": 0.65, "age_minutes": 1, "stale": false },
        "open_interest_change": { "raw": 0.08, "normalized": 0.72, "age_minutes": 1, "stale": false },
        "long_short_ratio": { "raw": 1.35, "normalized": 0.68, "age_minutes": 2, "stale": false },
        "liquidation_imbalance": { "raw": 0.7, "normalized": 0.70, "age_minutes": 1, "stale": false },
        "exchange_reserves_change": { "raw": -0.02, "normalized": 0.80, "age_minutes": 30, "stale": false }
      }
    },
    "onchain_flows": {
      "score": 0.71,
      "weight": 0.20,
      "contribution": 0.142,
      "components": {
        "stablecoin_flow": { "raw": 150000000, "normalized": 0.75, "age_minutes": 20, "stale": false },
        "btc_dominance_trend": { "raw": -0.5, "normalized": 0.65, "age_minutes": 15, "stale": false }
      }
    }
  },
  "contrarian_signal": null,
  "regime_enhancement": {
    "sentiment_regime": "greed",
    "volatility_regime": "normal",
    "combined_regime": "normal"
  },
  "data_quality": {
    "sources_available": 11,
    "sources_stale": 0,
    "sources_missing": 1,
    "coverage_pct": 0.917
  }
}
```

## Data Sources

### 1. Crowd Sentiment Sources

#### Crypto Fear & Greed Index (Alternative.me)

- **API**: `https://api.alternative.me/fng/`
- **Cost**: Free, no API key required
- **Rate Limit**: Reasonable (no strict limit documented)
- **Update Frequency**: Daily (new value every 24 hours)
- **Poll Interval**: Every 6 hours (check for updates, cache until new value)
- **Raw Range**: 0-100 (0 = Extreme Fear, 100 = Extreme Greed)
- **Normalization**: `raw_value / 100`
- **Staleness Threshold**: 48 hours (the index updates daily; stale if >48h old)

```java
public class FearGreedPoller implements SentimentPoller {
    private static final String API_URL = "https://api.alternative.me/fng/";
    private static final Duration POLL_INTERVAL = Duration.ofHours(6);
    private static final Duration STALENESS_THRESHOLD = Duration.ofHours(48);

    @Override
    public SentimentDataPoint poll() {
        JsonObject response = httpClient.get(API_URL).getAsJsonArray("data").get(0).getAsJsonObject();
        int rawValue = response.get("value").getAsInt();
        String classification = response.get("value_classification").getAsString();
        Instant timestamp = Instant.ofEpochSecond(response.get("timestamp").getAsLong());

        return SentimentDataPoint.builder()
            .source("fear_greed_index")
            .rawValue(rawValue)
            .normalizedValue(rawValue / 100.0)
            .timestamp(timestamp)
            .metadata(ImmutableMap.of("classification", classification))
            .build();
    }

    @Override
    public Duration pollInterval() { return POLL_INTERVAL; }

    @Override
    public Duration stalenessThreshold() { return STALENESS_THRESHOLD; }
}
```

#### Social Dominance (LunarCrush)

- **API**: LunarCrush v4 API
- **Cost**: Free tier (1000 req/day), Pro for higher limits
- **Rate Limit**: 1000 requests/day (free)
- **Update Frequency**: Every 15 minutes
- **Poll Interval**: Every 15 minutes
- **Raw Range**: 0-100 (percentage of total crypto social volume)
- **Normalization**: `min(raw_pct / 10.0, 1.0)` (10% dominance = max score; most assets are <5%)
- **Staleness Threshold**: 1 hour

#### Santiment Social Volume

- **API**: Santiment GraphQL API
- **Cost**: Free tier limited, Pro required for real-time
- **Rate Limit**: Rate limited per plan
- **Update Frequency**: Hourly
- **Poll Interval**: Every 1 hour
- **Raw Range**: Absolute mention count
- **Normalization**: Z-score against 30-day rolling mean, mapped to 0-1 via sigmoid
- **Staleness Threshold**: 3 hours

#### Google Trends

- **API**: Unofficial (pytrends library via Python sidecar)
- **Cost**: Free
- **Rate Limit**: Aggressive rate limiting; use careful backoff
- **Update Frequency**: Daily granularity
- **Poll Interval**: Every 6 hours
- **Raw Range**: 0-100 (relative search interest)
- **Normalization**: `raw_value / 100`
- **Staleness Threshold**: 24 hours

#### Reddit/X Mention Velocity

- **API**: LunarCrush or custom scraper via Python sidecar
- **Cost**: Varies by source
- **Rate Limit**: Source-dependent
- **Update Frequency**: Every 15 minutes
- **Poll Interval**: Every 15 minutes
- **Raw Range**: Mentions per hour (absolute count)
- **Normalization**: Current velocity / 7-day average velocity, capped at 2.0, then divided by 2.0
- **Staleness Threshold**: 1 hour

### 2. Market Structure Sources

#### Funding Rates (Binance, Bybit, OKX)

- **APIs**:
  - Binance: `GET /fapi/v1/fundingRate`
  - Bybit: `GET /v5/market/funding/history`
  - OKX: `GET /api/v5/public/funding-rate`
- **Cost**: Free, no API key required for public endpoints
- **Rate Limit**: Standard exchange limits (1200 req/min Binance, similar others)
- **Update Frequency**: Funding rates settle every 8 hours; current rate available continuously
- **Poll Interval**: Every 1 minute
- **Raw Range**: Typically -0.1% to +0.5% (extreme range)
- **Normalization**: See funding rate normalization below
- **Staleness Threshold**: 5 minutes

```java
public class FundingRateNormalizer {
    // Funding rate normalization:
    // Positive = longs pay shorts (bullish bias in market)
    // Negative = shorts pay longs (bearish bias)
    // We normalize to 0-1 where:
    //   0.5 = neutral (0% funding)
    //   >0.5 = bullish bias (positive funding)
    //   <0.5 = bearish bias (negative funding)
    //   Extreme values (>0.1% or <-0.05%) get clipped

    private static final double MAX_POSITIVE = 0.001;  // 0.1%
    private static final double MAX_NEGATIVE = -0.0005; // -0.05%

    public double normalize(double fundingRate) {
        if (fundingRate >= 0) {
            return 0.5 + 0.5 * Math.min(fundingRate / MAX_POSITIVE, 1.0);
        } else {
            return 0.5 - 0.5 * Math.min(Math.abs(fundingRate) / Math.abs(MAX_NEGATIVE), 1.0);
        }
    }

    // Cross-exchange median for robustness
    public double aggregateFundingRates(Map<String, Double> exchangeRates) {
        List<Double> rates = new ArrayList<>(exchangeRates.values());
        Collections.sort(rates);
        int mid = rates.size() / 2;
        return rates.size() % 2 == 0
            ? (rates.get(mid - 1) + rates.get(mid)) / 2.0
            : rates.get(mid);
    }
}
```

#### Open Interest

- **APIs**:
  - Binance: `GET /fapi/v1/openInterest`
  - Bybit: `GET /v5/market/open-interest`
  - OKX: `GET /api/v5/rubik/stat/contracts/open-interest-volume`
- **Cost**: Free
- **Poll Interval**: Every 1 minute
- **Raw Range**: Absolute USD value
- **Normalization**: 24-hour percentage change, mapped to 0-1 via:
  - `0.5 + 0.5 * clamp(pct_change / 0.20, -1, 1)` (20% change = full scale)
- **Staleness Threshold**: 5 minutes

#### Long/Short Ratio

- **APIs**:
  - Binance: `GET /futures/data/globalLongShortAccountRatio`
  - Bybit: `GET /v5/market/account-ratio`
- **Cost**: Free
- **Poll Interval**: Every 5 minutes
- **Raw Range**: Ratio (e.g., 1.5 means 60% long / 40% short)
- **Normalization**: `clamp((ratio - 0.5) / 2.0, 0, 1)` (0.5 ratio = 0.0, 2.5 ratio = 1.0)
- **Staleness Threshold**: 15 minutes

#### Liquidation Data

- **APIs**:
  - Binance WebSocket: `!forceOrder@arr`
  - CoinGlass API (aggregated)
- **Cost**: Free (Binance WS), CoinGlass has free tier
- **Poll Interval**: Every 1 minute (aggregate from WebSocket stream)
- **Raw Range**: USD value of liquidations per hour
- **Normalization**: Long liquidation ratio = `long_liqs / (long_liqs + short_liqs)`. Mapped to 0-1 where 0.5 = balanced.
- **Staleness Threshold**: 5 minutes

#### Exchange Reserve Data (CryptoQuant, Glassnode)

- **APIs**:
  - CryptoQuant: `GET /v1/btc/exchange-flows/reserve`
  - Glassnode: `GET /v1/metrics/distribution/exchange_net_position_change`
- **Cost**: CryptoQuant free tier limited; Glassnode requires paid plan
- **Poll Interval**: Every 5 minutes
- **Raw Range**: BTC/ETH units on exchanges
- **Normalization**: 24-hour change percentage, inverted (reserves decreasing = bullish = higher score):
  - `0.5 - 0.5 * clamp(pct_change / 0.05, -1, 1)`
- **Staleness Threshold**: 30 minutes

### 3. On-Chain Flow Sources

#### Stablecoin Flows

- **APIs**:
  - CryptoQuant: Stablecoin exchange flow
  - DefiLlama: `GET /stablecoins`
- **Cost**: DefiLlama free; CryptoQuant free tier limited
- **Poll Interval**: Every 15 minutes
- **Raw Range**: Net USD flow to exchanges (positive = inflow, negative = outflow)
- **Normalization**: `0.5 + 0.5 * clamp(net_flow / reference_flow, -1, 1)` where `reference_flow` is the 30-day average absolute daily flow
- **Staleness Threshold**: 1 hour

#### Bitcoin Dominance

- **API**: CoinGecko `GET /api/v3/global`
- **Cost**: Free (with rate limits)
- **Poll Interval**: Every 15 minutes
- **Raw Range**: Percentage (e.g., 52.3%)
- **Normalization**: 7-day trend direction. Increasing BTC dominance = risk-off (lower score for alts). Normalize 7-day change: `0.5 - 0.5 * clamp(dominance_change_pct / 3.0, -1, 1)`
- **Staleness Threshold**: 1 hour

## Implementation

### Core Data Model

```java
// SentimentDataPoint.java
@AutoValue
public abstract class SentimentDataPoint {
    public abstract String source();
    public abstract double rawValue();
    public abstract double normalizedValue();
    public abstract Instant timestamp();
    public abstract ImmutableMap<String, String> metadata();

    public boolean isStale(Duration threshold) {
        return Duration.between(timestamp(), Instant.now()).compareTo(threshold) > 0;
    }

    public static Builder builder() { return new AutoValue_SentimentDataPoint.Builder(); }

    @AutoValue.Builder
    public abstract static class Builder {
        public abstract Builder source(String source);
        public abstract Builder rawValue(double rawValue);
        public abstract Builder normalizedValue(double normalizedValue);
        public abstract Builder timestamp(Instant timestamp);
        public abstract Builder metadata(ImmutableMap<String, String> metadata);
        public abstract SentimentDataPoint build();
    }
}
```

```java
// CompositeSentimentScore.java
@AutoValue
public abstract class CompositeSentimentScore {
    public abstract String symbol();
    public abstract Instant timestamp();
    public abstract double compositeScore();
    public abstract ImmutableMap<String, CategoryScore> categoryScores();
    @Nullable public abstract ContrarianSignal contrarianSignal();
    public abstract RegimeEnhancement regimeEnhancement();
    public abstract DataQuality dataQuality();

    public static Builder builder() { return new AutoValue_CompositeSentimentScore.Builder(); }

    @AutoValue.Builder
    public abstract static class Builder {
        public abstract Builder symbol(String symbol);
        public abstract Builder timestamp(Instant timestamp);
        public abstract Builder compositeScore(double compositeScore);
        public abstract Builder categoryScores(ImmutableMap<String, CategoryScore> categoryScores);
        public abstract Builder contrarianSignal(@Nullable ContrarianSignal contrarianSignal);
        public abstract Builder regimeEnhancement(RegimeEnhancement regimeEnhancement);
        public abstract Builder dataQuality(DataQuality dataQuality);
        public abstract CompositeSentimentScore build();
    }
}

@AutoValue
public abstract class CategoryScore {
    public abstract double score();
    public abstract double weight();
    public abstract double contribution();
    public abstract ImmutableMap<String, ComponentScore> components();
}

@AutoValue
public abstract class DataQuality {
    public abstract int sourcesAvailable();
    public abstract int sourcesStale();
    public abstract int sourcesMissing();

    public double coveragePct() {
        int total = sourcesAvailable() + sourcesMissing();
        return total > 0 ? (double) sourcesAvailable() / total : 0.0;
    }
}
```

### Poller Framework

```java
// SentimentPoller.java
public interface SentimentPoller {
    String sourceName();
    Duration pollInterval();
    Duration stalenessThreshold();
    SentimentDataPoint poll() throws PollerException;
}

// PollerScheduler.java
public class PollerScheduler {
    private final ImmutableList<SentimentPoller> pollers;
    private final ScheduledExecutorService executor;
    private final SentimentDataStore dataStore;
    private final MetricsRegistry metrics;

    @Inject
    PollerScheduler(
            ImmutableList<SentimentPoller> pollers,
            SentimentDataStore dataStore,
            MetricsRegistry metrics) {
        this.pollers = pollers;
        this.dataStore = dataStore;
        this.metrics = metrics;
        this.executor = Executors.newScheduledThreadPool(pollers.size());
    }

    public void start() {
        for (SentimentPoller poller : pollers) {
            executor.scheduleAtFixedRate(
                () -> pollSafely(poller),
                /* initialDelay= */ 0,
                poller.pollInterval().toSeconds(),
                TimeUnit.SECONDS
            );
            logger.atInfo().log("Scheduled poller %s every %s", poller.sourceName(), poller.pollInterval());
        }
    }

    private void pollSafely(SentimentPoller poller) {
        Stopwatch stopwatch = Stopwatch.createStarted();
        try {
            SentimentDataPoint dataPoint = poller.poll();
            dataStore.store(dataPoint);
            metrics.recordLatency("sentiment_poll_latency_ms", poller.sourceName(), stopwatch.elapsed().toMillis());
            metrics.increment("sentiment_poll_success", poller.sourceName());
        } catch (PollerException e) {
            logger.atWarning().withCause(e).log("Poller %s failed", poller.sourceName());
            metrics.increment("sentiment_poll_failure", poller.sourceName());
        }
    }

    public void shutdown() {
        executor.shutdown();
        try {
            executor.awaitTermination(10, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
```

### Composite Scoring Engine

```java
// CompositeSentimentScorer.java
public class CompositeSentimentScorer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final SentimentDataStore dataStore;
    private final SentimentConfig config;
    private final ContrarianDetector contrarianDetector;
    private final RegimeEnhancer regimeEnhancer;

    @Inject
    CompositeSentimentScorer(
            SentimentDataStore dataStore,
            SentimentConfig config,
            ContrarianDetector contrarianDetector,
            RegimeEnhancer regimeEnhancer) {
        this.dataStore = dataStore;
        this.config = config;
        this.contrarianDetector = contrarianDetector;
        this.regimeEnhancer = regimeEnhancer;
    }

    public CompositeSentimentScore computeScore(String symbol) {
        Instant now = Instant.now();

        // Gather latest data points for each source
        ImmutableMap<String, SentimentDataPoint> latestData = dataStore.getLatestForSymbol(symbol);

        // Compute category scores with missing data handling
        CategoryScore crowdScore = computeCategoryScore(
            latestData,
            config.crowdSentimentSources(),
            config.crowdSentimentWeight()
        );
        CategoryScore structureScore = computeCategoryScore(
            latestData,
            config.marketStructureSources(),
            config.marketStructureWeight()
        );
        CategoryScore onchainScore = computeCategoryScore(
            latestData,
            config.onchainFlowSources(),
            config.onchainFlowWeight()
        );

        // Weighted composite
        double composite = crowdScore.contribution()
            + structureScore.contribution()
            + onchainScore.contribution();

        // Renormalize if some categories are entirely missing
        double totalActiveWeight = 0;
        if (crowdScore.components().size() > 0) totalActiveWeight += config.crowdSentimentWeight();
        if (structureScore.components().size() > 0) totalActiveWeight += config.marketStructureWeight();
        if (onchainScore.components().size() > 0) totalActiveWeight += config.onchainFlowWeight();

        if (totalActiveWeight > 0 && totalActiveWeight < 1.0) {
            composite = composite / totalActiveWeight;
        }

        // Detect contrarian signals
        ContrarianSignal contrarianSignal = contrarianDetector.detect(latestData, composite);

        // Enhance market regime
        RegimeEnhancement regimeEnhancement = regimeEnhancer.enhance(symbol, composite, latestData);

        // Data quality metrics
        int totalSources = config.allSourceNames().size();
        int availableSources = (int) latestData.values().stream()
            .filter(dp -> !dp.isStale(config.stalenessThreshold(dp.source())))
            .count();
        int staleSources = (int) latestData.values().stream()
            .filter(dp -> dp.isStale(config.stalenessThreshold(dp.source())))
            .count();
        int missingSources = totalSources - latestData.size();

        return CompositeSentimentScore.builder()
            .symbol(symbol)
            .timestamp(now)
            .compositeScore(composite)
            .categoryScores(ImmutableMap.of(
                "crowd_sentiment", crowdScore,
                "market_structure", structureScore,
                "onchain_flows", onchainScore
            ))
            .contrarianSignal(contrarianSignal)
            .regimeEnhancement(regimeEnhancement)
            .dataQuality(DataQuality.create(availableSources, staleSources, missingSources))
            .build();
    }

    private CategoryScore computeCategoryScore(
            ImmutableMap<String, SentimentDataPoint> allData,
            ImmutableList<SourceConfig> sources,
            double categoryWeight) {

        ImmutableMap.Builder<String, ComponentScore> components = ImmutableMap.builder();
        double weightedSum = 0;
        double totalWeight = 0;

        for (SourceConfig source : sources) {
            SentimentDataPoint dataPoint = allData.get(source.name());

            if (dataPoint == null) {
                // Missing source: skip, weight redistributed to available sources
                logger.atFine().log("Source %s missing, redistributing weight", source.name());
                continue;
            }

            boolean stale = dataPoint.isStale(source.stalenessThreshold());
            double effectiveWeight = stale
                ? source.withinCategoryWeight() * config.staleDataPenalty()
                : source.withinCategoryWeight();

            weightedSum += dataPoint.normalizedValue() * effectiveWeight;
            totalWeight += effectiveWeight;

            components.put(source.name(), ComponentScore.create(
                dataPoint.rawValue(),
                dataPoint.normalizedValue(),
                Duration.between(dataPoint.timestamp(), Instant.now()).toMinutes(),
                stale
            ));
        }

        double categoryScore = totalWeight > 0 ? weightedSum / totalWeight : 0.5;

        return CategoryScore.create(
            categoryScore,
            categoryWeight,
            categoryScore * categoryWeight,
            components.build()
        );
    }
}
```

### Missing Data Handling

Sources update at different frequencies. The system handles this with a tiered strategy:

```
+-----------------------------------------------------------------+
| MISSING DATA HANDLING STRATEGY                                  |
|                                                                 |
| 1. Source available and fresh  -> Use normalized value at full  |
|                                   weight                        |
|                                                                 |
| 2. Source available but stale  -> Use normalized value at       |
|    (age > staleness threshold)    reduced weight (50% penalty)  |
|                                                                 |
| 3. Source unavailable          -> Redistribute weight to        |
|    (poll failed / no data)        remaining sources in same     |
|                                   category                      |
|                                                                 |
| 4. Entire category missing     -> Renormalize composite using  |
|    (all sources in category       only available categories     |
|     unavailable)                                                |
|                                                                 |
| 5. All sources missing         -> Return 0.5 (neutral) with   |
|    (system degraded)              data_quality.coverage = 0    |
+-----------------------------------------------------------------+
```

### Contrarian Signal Detection

```java
// ContrarianDetector.java
public class ContrarianDetector {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final SentimentConfig config;

    @Inject
    ContrarianDetector(SentimentConfig config) {
        this.config = config;
    }

    @Nullable
    public ContrarianSignal detect(
            ImmutableMap<String, SentimentDataPoint> data,
            double compositeScore) {

        SentimentDataPoint fearGreed = data.get("fear_greed_index");
        if (fearGreed == null) {
            return null;
        }

        double fgValue = fearGreed.rawValue();

        // Extreme Fear (<20): Historically a buying opportunity
        // Market participants are panic selling, creating discounted entries.
        // Bitcoin has averaged +22% returns in the 30 days following
        // Fear & Greed readings below 20 (2018-2025 data).
        if (fgValue < config.extremeFearThreshold()) {
            double intensity = 1.0 - (fgValue / config.extremeFearThreshold());
            return ContrarianSignal.create(
                ContrarianType.EXTREME_FEAR_BUY,
                intensity,
                String.format(
                    "Fear & Greed at %.0f (Extreme Fear). "
                    + "Historically, readings below %d precede positive 30-day returns "
                    + "with %.0f%% probability. Consider accumulation.",
                    fgValue,
                    config.extremeFearThreshold(),
                    config.extremeFearWinRate() * 100
                )
            );
        }

        // Extreme Greed (>80): Historically signals caution
        // Market is euphoric, late entrants are buying, smart money distributing.
        // Risk of blow-off top increases significantly above 80.
        if (fgValue > config.extremeGreedThreshold()) {
            double intensity = (fgValue - config.extremeGreedThreshold())
                / (100.0 - config.extremeGreedThreshold());
            return ContrarianSignal.create(
                ContrarianType.EXTREME_GREED_CAUTION,
                intensity,
                String.format(
                    "Fear & Greed at %.0f (Extreme Greed). "
                    + "Readings above %d historically precede corrections within "
                    + "14 days %.0f%% of the time. Consider reducing exposure.",
                    fgValue,
                    config.extremeGreedThreshold(),
                    config.extremeGreedCorrectionRate() * 100
                )
            );
        }

        // Composite-level contrarian: check if funding rates diverge from sentiment
        SentimentDataPoint fundingRate = data.get("funding_rate");
        if (fundingRate != null) {
            double fundingNorm = fundingRate.normalizedValue();

            // High crowd sentiment + very negative funding = potential short squeeze
            if (compositeScore > 0.65 && fundingNorm < 0.25) {
                return ContrarianSignal.create(
                    ContrarianType.SHORT_SQUEEZE_SETUP,
                    0.6,
                    "Positive sentiment with negative funding rates. "
                    + "Short-side crowding creates squeeze potential."
                );
            }

            // Low crowd sentiment + very positive funding = potential long squeeze
            if (compositeScore < 0.35 && fundingNorm > 0.80) {
                return ContrarianSignal.create(
                    ContrarianType.LONG_SQUEEZE_SETUP,
                    0.6,
                    "Negative sentiment with high positive funding. "
                    + "Long-side crowding creates cascade liquidation risk."
                );
            }
        }

        return null;
    }
}

@AutoValue
public abstract class ContrarianSignal {
    public abstract ContrarianType type();
    public abstract double intensity();  // 0-1, higher = stronger signal
    public abstract String reasoning();

    public static ContrarianSignal create(ContrarianType type, double intensity, String reasoning) {
        return new AutoValue_ContrarianSignal(type, Math.min(1.0, Math.max(0.0, intensity)), reasoning);
    }
}

public enum ContrarianType {
    EXTREME_FEAR_BUY,
    EXTREME_GREED_CAUTION,
    SHORT_SQUEEZE_SETUP,
    LONG_SQUEEZE_SETUP
}
```

### Market Regime Enhancement

The existing market regime detection uses only volatility percentile. This enhancement adds sentiment data for a richer regime classification:

```java
// RegimeEnhancer.java
public class RegimeEnhancer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final SentimentConfig config;

    @Inject
    RegimeEnhancer(SentimentConfig config) {
        this.config = config;
    }

    /**
     * Enhance market regime detection with sentiment data.
     *
     * The combined regime matrix:
     *
     *                     |  Low Volatility  |  High Volatility  |  Extreme Volatility
     * --------------------|------------------|-------------------|---------------------
     * Extreme Fear (<0.2) |  Accumulation    |  Capitulation     |  Capitulation
     * Fear (0.2-0.4)      |  Normal          |  Correction       |  Capitulation
     * Neutral (0.4-0.6)   |  Normal          |  High Volatility  |  Extreme
     * Greed (0.6-0.8)     |  Normal          |  Blow-off Risk    |  Blow-off Top
     * Extreme Greed (>0.8)|  Overextended    |  Blow-off Top     |  Blow-off Top
     */
    public RegimeEnhancement enhance(
            String symbol,
            double compositeScore,
            ImmutableMap<String, SentimentDataPoint> data) {

        String sentimentRegime = classifySentimentRegime(compositeScore);
        String volatilityRegime = getVolatilityRegime(symbol);
        String combinedRegime = combinedRegime(sentimentRegime, volatilityRegime);

        return RegimeEnhancement.create(sentimentRegime, volatilityRegime, combinedRegime);
    }

    private String classifySentimentRegime(double compositeScore) {
        if (compositeScore < 0.2) return "extreme_fear";
        if (compositeScore < 0.4) return "fear";
        if (compositeScore < 0.6) return "neutral";
        if (compositeScore < 0.8) return "greed";
        return "extreme_greed";
    }

    private String combinedRegime(String sentimentRegime, String volatilityRegime) {
        // Capitulation: extreme fear + high/extreme volatility
        // This is a potential buying opportunity - panic selling creates discounts
        if ((sentimentRegime.equals("extreme_fear") || sentimentRegime.equals("fear"))
                && (volatilityRegime.equals("high_volatility") || volatilityRegime.equals("extreme"))) {
            return "capitulation";
        }

        // Blow-off top: extreme greed + high/extreme volatility
        // This is a risk signal - euphoria + volatility = potential crash
        if ((sentimentRegime.equals("extreme_greed") || sentimentRegime.equals("greed"))
                && (volatilityRegime.equals("high_volatility") || volatilityRegime.equals("extreme"))) {
            return "blow_off_top";
        }

        // Overextended: extreme greed + low volatility
        // Market is complacent - historically precedes volatility spikes
        if (sentimentRegime.equals("extreme_greed") && volatilityRegime.equals("normal")) {
            return "overextended";
        }

        // Accumulation: extreme fear + low volatility
        // Smart money accumulating while retail is fearful
        if (sentimentRegime.equals("extreme_fear") && volatilityRegime.equals("normal")) {
            return "accumulation";
        }

        // Default: use volatility regime as-is
        return volatilityRegime;
    }

    private String getVolatilityRegime(String symbol) {
        // Delegates to existing regime detection
        // See opportunity-scoring spec: detect_market_regime()
        double percentile = marketDataService.getHistoricalVolatilityPercentile(symbol, 30);
        if (percentile >= 0.95) return "extreme";
        if (percentile >= 0.80) return "high_volatility";
        return "normal";
    }
}

@AutoValue
public abstract class RegimeEnhancement {
    public abstract String sentimentRegime();
    public abstract String volatilityRegime();
    public abstract String combinedRegime();

    public static RegimeEnhancement create(String sentiment, String volatility, String combined) {
        return new AutoValue_RegimeEnhancement(sentiment, volatility, combined);
    }
}
```

### Kafka Publishing

```java
// SentimentKafkaPublisher.java
public class SentimentKafkaPublisher {
    private static final String TOPIC = "sentiment.scores";

    private final KafkaProducer<String, byte[]> producer;

    @Inject
    SentimentKafkaPublisher(KafkaProducer<String, byte[]> producer) {
        this.producer = producer;
    }

    public void publish(CompositeSentimentScore score) {
        SentimentScoreProto proto = toProto(score);
        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            TOPIC,
            score.symbol(),
            proto.toByteArray()
        );
        producer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.atSevere().withCause(exception).log(
                    "Failed to publish sentiment score for %s", score.symbol());
            }
        });
    }
}
```

### Historical Tracking (InfluxDB)

```java
// SentimentInfluxWriter.java
public class SentimentInfluxWriter {
    private static final String MEASUREMENT = "sentiment_scores";
    private static final String BUCKET = "tradestream";

    private final WriteApi writeApi;

    @Inject
    SentimentInfluxWriter(InfluxDBClient influxClient) {
        this.writeApi = influxClient.makeWriteApi();
    }

    public void write(CompositeSentimentScore score) {
        Point point = Point.measurement(MEASUREMENT)
            .time(score.timestamp(), WritePrecision.S)
            .addTag("symbol", score.symbol())
            .addField("composite_score", score.compositeScore())
            .addField("crowd_sentiment", score.categoryScores().get("crowd_sentiment").score())
            .addField("market_structure", score.categoryScores().get("market_structure").score())
            .addField("onchain_flows", score.categoryScores().get("onchain_flows").score())
            .addField("sentiment_regime", score.regimeEnhancement().sentimentRegime())
            .addField("combined_regime", score.regimeEnhancement().combinedRegime())
            .addField("data_coverage_pct", score.dataQuality().coveragePct());

        // Write individual component scores for analysis
        for (Map.Entry<String, CategoryScore> category : score.categoryScores().entrySet()) {
            for (Map.Entry<String, ComponentScore> component : category.getValue().components().entrySet()) {
                point.addField(component.getKey() + "_normalized", component.getValue().normalizedValue());
            }
        }

        if (score.contrarianSignal() != null) {
            point.addField("contrarian_type", score.contrarianSignal().type().name());
            point.addField("contrarian_intensity", score.contrarianSignal().intensity());
        }

        writeApi.writePoint(BUCKET, "tradestream", point);
    }
}
```

## Integration with Opportunity Scoring

### Adding `market_sentiment_score` to the Formula

The existing opportunity scoring formula is extended with a sentiment factor. The total weight budget is redistributed:

| Factor | Current Weight | New Weight | Change |
|--------|---------------|------------|--------|
| Confidence | 25% | 22% | -3% |
| Expected Return | 30% | 27% | -3% |
| Strategy Consensus | 20% | 18% | -2% |
| Volatility Factor | 15% | 13% | -2% |
| Freshness | 10% | 10% | 0% |
| **Market Sentiment** | **--** | **10%** | **+10%** |

**Rationale**: Sentiment gets 10% weight as a supplementary signal. It should influence scoring without overriding technical analysis. Weight is redistributed proportionally from the four technical factors, preserving their relative importance. Freshness remains unchanged as it serves a different purpose (time decay).

```python
def calculate_opportunity_score(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    market_regime: str = "normal",
    market_sentiment_score: float = 0.5,  # NEW: 0-1, default neutral
    contrarian_signal: Optional[dict] = None  # NEW: contrarian override
) -> float:
    """
    Calculate opportunity score (0-100) with sentiment integration.
    """
    caps = get_regime_adjusted_caps(market_regime)

    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)
    volatility_score = min(volatility / caps.max_volatility, 1.0)
    freshness_score = max(0, 1 - (minutes_ago / 60))

    # Sentiment score is already 0-1
    sentiment_score = market_sentiment_score

    # Weighted sum with new weights
    opportunity_score = (
        0.22 * confidence +
        0.27 * return_score +
        0.18 * consensus_pct +
        0.13 * volatility_score +
        0.10 * freshness_score +
        0.10 * sentiment_score       # NEW
    ) * 100

    # Apply contrarian bonus/penalty
    if contrarian_signal:
        adjustment = calculate_contrarian_adjustment(contrarian_signal, opportunity_score)
        opportunity_score += adjustment

    return round(max(0, min(100, opportunity_score)), 1)


def calculate_contrarian_adjustment(
    contrarian_signal: dict,
    base_score: float
) -> float:
    """
    Adjust opportunity score based on contrarian signals.

    Extreme fear on a BUY signal = bonus (opportunity)
    Extreme greed on a BUY signal = penalty (caution)
    """
    signal_type = contrarian_signal["type"]
    intensity = contrarian_signal["intensity"]

    if signal_type == "EXTREME_FEAR_BUY":
        # Boost BUY scores during extreme fear (max +10 points)
        return intensity * 10.0

    elif signal_type == "EXTREME_GREED_CAUTION":
        # Penalize BUY scores during extreme greed (max -8 points)
        return -intensity * 8.0

    elif signal_type == "SHORT_SQUEEZE_SETUP":
        # Moderate boost for squeeze setups (max +5 points)
        return intensity * 5.0

    elif signal_type == "LONG_SQUEEZE_SETUP":
        # Moderate penalty for long squeeze risk (max -5 points)
        return -intensity * 5.0

    return 0.0
```

### Enhanced Market Regime Integration

The opportunity scorer's `detect_market_regime` function is enhanced to use the combined regime from sentiment data:

```python
def detect_market_regime_enhanced(
    symbol: str,
    sentiment_score: CompositeSentimentScore
) -> str:
    """
    Enhanced market regime detection using sentiment + volatility.

    Returns one of:
    - normal, high_volatility, extreme (original)
    - capitulation, blow_off_top, accumulation, overextended (new)
    """
    combined_regime = sentiment_score.regime_enhancement.combined_regime

    # Use sentiment-enhanced regime if available, fall back to volatility-only
    if combined_regime in ("capitulation", "blow_off_top", "accumulation", "overextended"):
        return combined_regime

    # Fall back to existing volatility-only detection
    return detect_market_regime(symbol)
```

### Regime-Adjusted Caps (Extended)

```python
def get_regime_adjusted_caps(regime: str) -> RegimeCaps:
    """Extended regime caps including sentiment-derived regimes."""

    # Existing regimes
    if regime == "extreme":
        return RegimeCaps(max_return=0.15, max_volatility=0.10)
    elif regime == "high_volatility":
        return RegimeCaps(max_return=0.08, max_volatility=0.05)

    # New sentiment-derived regimes
    elif regime == "capitulation":
        # Wider caps: opportunities are large during capitulation
        return RegimeCaps(max_return=0.20, max_volatility=0.12)
    elif regime == "blow_off_top":
        # Tighter caps: risk management during euphoria
        return RegimeCaps(max_return=0.05, max_volatility=0.04)
    elif regime == "accumulation":
        # Normal caps but slightly wider for returns
        return RegimeCaps(max_return=0.07, max_volatility=0.03)
    elif regime == "overextended":
        # Tighter caps: caution during complacent markets
        return RegimeCaps(max_return=0.04, max_volatility=0.025)

    else:  # normal
        return RegimeCaps(max_return=0.05, max_volatility=0.03)
```

### Scored Signal Format (Extended)

```json
{
  "signal_id": "sig-abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "opportunity_score": 91.2,
  "opportunity_factors": {
    "confidence": { "value": 0.82, "contribution": 18.0 },
    "expected_return": { "value": 0.032, "contribution": 27.0 },
    "consensus": { "value": 0.80, "contribution": 14.4 },
    "volatility": { "value": 0.021, "contribution": 9.1 },
    "freshness": { "value": 0, "contribution": 10.0 },
    "market_sentiment": {
      "value": 0.18,
      "contribution": 1.8,
      "regime": "capitulation",
      "contrarian": {
        "type": "EXTREME_FEAR_BUY",
        "intensity": 0.82,
        "adjustment": 8.2
      }
    }
  },
  "market_regime": "capitulation"
}
```

## Historical Backtesting

Track composite sentiment vs. subsequent returns to validate the model over time.

### Backtesting Schema (InfluxDB)

```
measurement: sentiment_backtest
tags: symbol, sentiment_bucket (extreme_fear, fear, neutral, greed, extreme_greed)
fields:
  - composite_score: float
  - return_7d: float     (% return 7 days after score recorded)
  - return_14d: float    (% return 14 days after score recorded)
  - return_30d: float    (% return 30 days after score recorded)
  - contrarian_active: boolean
  - regime: string
```

### Backtest Runner

```java
// SentimentBacktester.java
public class SentimentBacktester {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final ImmutableList<Integer> FORWARD_RETURN_DAYS = ImmutableList.of(7, 14, 30);

    private final InfluxDBClient influxClient;
    private final MarketDataService marketDataService;

    @Inject
    SentimentBacktester(InfluxDBClient influxClient, MarketDataService marketDataService) {
        this.influxClient = influxClient;
        this.marketDataService = marketDataService;
    }

    /**
     * Run daily: look back at sentiment scores from N days ago,
     * compute the forward return, and store the result.
     */
    public void computeForwardReturns(String symbol) {
        for (int days : FORWARD_RETURN_DAYS) {
            Instant lookbackTime = Instant.now().minus(Duration.ofDays(days));

            // Get sentiment score from N days ago
            Optional<CompositeSentimentScore> historicalScore =
                getHistoricalSentimentScore(symbol, lookbackTime);

            if (historicalScore.isEmpty()) {
                continue;
            }

            // Get price at that time and current price
            double priceAtScore = marketDataService.getHistoricalPrice(symbol, lookbackTime);
            double currentPrice = marketDataService.getCurrentPrice(symbol);
            double forwardReturn = (currentPrice - priceAtScore) / priceAtScore;

            // Store backtest result
            String sentimentBucket = bucketize(historicalScore.get().compositeScore());

            Point point = Point.measurement("sentiment_backtest")
                .time(lookbackTime, WritePrecision.S)
                .addTag("symbol", symbol)
                .addTag("sentiment_bucket", sentimentBucket)
                .addField("composite_score", historicalScore.get().compositeScore())
                .addField("return_" + days + "d", forwardReturn)
                .addField("contrarian_active", historicalScore.get().contrarianSignal() != null)
                .addField("regime", historicalScore.get().regimeEnhancement().combinedRegime());

            influxClient.makeWriteApi().writePoint("tradestream", "tradestream", point);

            logger.atInfo().log(
                "Backtest %s: sentiment=%.2f bucket=%s %dd_return=%.4f",
                symbol, historicalScore.get().compositeScore(), sentimentBucket, days, forwardReturn);
        }
    }

    private String bucketize(double score) {
        if (score < 0.2) return "extreme_fear";
        if (score < 0.4) return "fear";
        if (score < 0.6) return "neutral";
        if (score < 0.8) return "greed";
        return "extreme_greed";
    }

    /**
     * Generate validation report: average forward returns by sentiment bucket.
     */
    public BacktestReport generateReport(String symbol, int lookbackDays) {
        String query = String.format(
            "from(bucket: \"tradestream\") "
            + "|> range(start: -%dd) "
            + "|> filter(fn: (r) => r._measurement == \"sentiment_backtest\" "
            + "   and r.symbol == \"%s\") "
            + "|> group(columns: [\"sentiment_bucket\"])",
            lookbackDays, symbol
        );

        // Query and aggregate results
        // Returns: avg return per sentiment bucket per time horizon
        // Used to validate contrarian hypothesis:
        //   extreme_fear should have positive forward returns
        //   extreme_greed should have negative or lower forward returns
        return queryAndAggregate(query);
    }
}
```

### Validation Criteria

The sentiment model is considered validated when backtesting shows:

| Sentiment Bucket | Expected 7d Return | Expected 30d Return |
|-----------------|--------------------|--------------------|
| Extreme Fear (<0.2) | > 0% (positive) | > +5% |
| Fear (0.2-0.4) | > -2% | > 0% |
| Neutral (0.4-0.6) | Market average | Market average |
| Greed (0.6-0.8) | < market average | < market average |
| Extreme Greed (>0.8) | < 0% | < -3% |

If backtesting shows the contrarian hypothesis does not hold for a given asset, the contrarian adjustment weight should be reduced for that asset via configuration.

## Configuration

```yaml
sentiment_indices:
  # Category weights (must sum to 1.0)
  weights:
    crowd_sentiment: 0.35
    market_structure: 0.45
    onchain_flows: 0.20

  # Staleness and degradation
  stale_data_penalty: 0.5          # Reduce stale source weight by 50%
  min_coverage_for_scoring: 0.3    # Need at least 30% of sources to score
  default_neutral_score: 0.5       # Score when all sources missing

  # Contrarian thresholds
  contrarian:
    extreme_fear_threshold: 20      # Fear & Greed < 20 triggers buy signal
    extreme_greed_threshold: 80     # Fear & Greed > 80 triggers caution
    extreme_fear_win_rate: 0.78     # Historical win rate for contrarian buys
    extreme_greed_correction_rate: 0.65  # Historical correction probability
    contrarian_score_bonus_max: 10  # Max +/- points to opportunity score
    enabled: true

  # Opportunity scoring integration
  opportunity_scoring:
    sentiment_weight: 0.10          # Weight in opportunity score formula
    # Redistributed weights (must sum to 0.90 with sentiment)
    confidence_weight: 0.22
    expected_return_weight: 0.27
    consensus_weight: 0.18
    volatility_weight: 0.13
    freshness_weight: 0.10

  # Regime enhancement
  regime:
    capitulation_caps:
      max_return: 0.20
      max_volatility: 0.12
    blow_off_top_caps:
      max_return: 0.05
      max_volatility: 0.04
    accumulation_caps:
      max_return: 0.07
      max_volatility: 0.03
    overextended_caps:
      max_return: 0.04
      max_volatility: 0.025

  # Source-specific configuration
  sources:
    fear_greed_index:
      enabled: true
      poll_interval_seconds: 21600   # 6 hours
      staleness_threshold_seconds: 172800  # 48 hours
      within_category_weight: 0.30
    social_dominance:
      enabled: true
      poll_interval_seconds: 900     # 15 minutes
      staleness_threshold_seconds: 3600    # 1 hour
      within_category_weight: 0.20
      api_key: "${LUNARCRUSH_API_KEY}"
    santiment:
      enabled: true
      poll_interval_seconds: 3600    # 1 hour
      staleness_threshold_seconds: 10800   # 3 hours
      within_category_weight: 0.15
      api_key: "${SANTIMENT_API_KEY}"
    google_trends:
      enabled: true
      poll_interval_seconds: 21600   # 6 hours
      staleness_threshold_seconds: 86400   # 24 hours
      within_category_weight: 0.15
    mention_velocity:
      enabled: true
      poll_interval_seconds: 900     # 15 minutes
      staleness_threshold_seconds: 3600    # 1 hour
      within_category_weight: 0.20
    funding_rate:
      enabled: true
      poll_interval_seconds: 60      # 1 minute
      staleness_threshold_seconds: 300     # 5 minutes
      within_category_weight: 0.25
      exchanges:
        - binance
        - bybit
        - okx
    open_interest:
      enabled: true
      poll_interval_seconds: 60      # 1 minute
      staleness_threshold_seconds: 300     # 5 minutes
      within_category_weight: 0.25
    long_short_ratio:
      enabled: true
      poll_interval_seconds: 300     # 5 minutes
      staleness_threshold_seconds: 900     # 15 minutes
      within_category_weight: 0.20
    liquidation_data:
      enabled: true
      poll_interval_seconds: 60      # 1 minute
      staleness_threshold_seconds: 300     # 5 minutes
      within_category_weight: 0.15
    exchange_reserves:
      enabled: true
      poll_interval_seconds: 300     # 5 minutes
      staleness_threshold_seconds: 1800    # 30 minutes
      within_category_weight: 0.15
      api_key: "${CRYPTOQUANT_API_KEY}"
    stablecoin_flow:
      enabled: true
      poll_interval_seconds: 900     # 15 minutes
      staleness_threshold_seconds: 3600    # 1 hour
      within_category_weight: 0.55
    btc_dominance:
      enabled: true
      poll_interval_seconds: 900     # 15 minutes
      staleness_threshold_seconds: 3600    # 1 hour
      within_category_weight: 0.45

  # Kafka
  kafka:
    topic: "sentiment.scores"
    key_serializer: "org.apache.kafka.common.serialization.StringSerializer"
    value_serializer: "org.apache.kafka.common.serialization.ByteArraySerializer"

  # InfluxDB historical tracking
  influxdb:
    bucket: "tradestream"
    measurement: "sentiment_scores"
    retention_days: 365

  # Backtesting
  backtesting:
    enabled: true
    schedule: "0 0 * * *"           # Daily at midnight UTC
    forward_return_days: [7, 14, 30]
    min_data_points_for_validation: 90  # 90 days of data before trusting results

  # Redis cache
  cache:
    key_prefix: "sentiment:"
    composite_score_ttl_seconds: 60
    individual_source_ttl_seconds: 300
```

## Constraints

- All external API calls must have timeouts (5 second default)
- Individual poller failures must not block other pollers or the composite score
- Composite score must always be available (fall back to 0.5 neutral if all sources fail)
- Scores published to Kafka within 1 second of computation
- Historical data retained for 365 days in InfluxDB for backtesting
- All API keys stored as Kubernetes secrets, never in configuration files
- Rate limiting must respect each source's documented limits
- Must not add more than 100ms to opportunity score calculation latency
- The system must function with 0 external sources configured (returns neutral score)
- Contrarian adjustments are bounded: max +10 / -8 points to opportunity score

## Non-Goals

- **Trade execution**: Sentiment data informs scoring only; it does not trigger trades directly
- **Proprietary data collection**: No scraping or custom NLP on social media; rely on existing aggregated APIs
- **Real-time WebSocket for all sources**: Only liquidation data uses WebSocket; everything else is polled
- **Per-user sentiment preferences**: All users see the same sentiment-weighted scores (user customization is a separate spec)
- **Sentiment prediction / forecasting**: The system reports current sentiment, not future sentiment
- **NPS-like community surveys**: Deferred to a future community engagement spec; not included in initial implementation

## Acceptance Criteria

- [ ] Fear & Greed Index polled and normalized to 0-1
- [ ] Social dominance data from LunarCrush integrated
- [ ] Google Trends search volume for crypto terms integrated
- [ ] Reddit/X mention velocity tracked and normalized
- [ ] Funding rates aggregated across Binance, Bybit, OKX via median
- [ ] Open interest changes tracked and normalized
- [ ] Long/short ratios integrated from at least 2 exchanges
- [ ] Liquidation data collected and imbalance computed
- [ ] Exchange reserve changes tracked (CryptoQuant)
- [ ] Stablecoin flows (net exchange flow) integrated
- [ ] Bitcoin dominance trend computed and normalized
- [ ] Composite sentiment score (0-1) computed from weighted categories
- [ ] Missing data handled gracefully: stale penalty, weight redistribution, neutral fallback
- [ ] Contrarian signals generated for Fear & Greed < 20 and > 80
- [ ] Contrarian signals generated for funding rate / sentiment divergence
- [ ] Market regime enhanced with sentiment: capitulation, blow-off top, accumulation, overextended
- [ ] `market_sentiment_score` integrated into opportunity scoring formula at 10% weight
- [ ] Contrarian adjustments applied to opportunity score (bounded +10 / -8)
- [ ] Regime-adjusted caps defined for all new sentiment-derived regimes
- [ ] Sentiment scores published to Kafka topic `sentiment.scores`
- [ ] Historical sentiment data stored in InfluxDB with 365-day retention
- [ ] Daily backtesting job computes forward returns by sentiment bucket
- [ ] Backtest validation report confirms contrarian hypothesis directionally
- [ ] All pollers respect external API rate limits
- [ ] Individual poller failures do not block composite scoring
- [ ] Score computation adds < 100ms to opportunity scoring latency
- [ ] Prometheus metrics emitted for poll success/failure, latency, coverage
- [ ] Guice module binds all pollers, scorers, and publishers

## File Structure

```
src/main/java/com/verlumen/tradestream/sentiment/
|-- SentimentModule.kt                    # Guice module binding all components
|-- SentimentDataPoint.java               # Core data model
|-- CompositeSentimentScore.java          # Composite score with categories
|-- ContrarianSignal.java                 # Contrarian signal detection result
|-- RegimeEnhancement.java                # Regime classification result
|-- DataQuality.java                      # Data quality metrics
|-- scoring/
|   |-- CompositeSentimentScorer.java     # Main scoring engine
|   |-- ContrarianDetector.java           # Contrarian signal detection
|   |-- RegimeEnhancer.java              # Market regime enhancement
|   |-- BUILD
|-- pollers/
|   |-- SentimentPoller.java             # Poller interface
|   |-- PollerScheduler.java            # Scheduled poller orchestrator
|   |-- crowd/
|   |   |-- FearGreedPoller.java
|   |   |-- SocialDominancePoller.java
|   |   |-- GoogleTrendsPoller.java
|   |   |-- MentionVelocityPoller.java
|   |   |-- BUILD
|   |-- structure/
|   |   |-- FundingRatePoller.java
|   |   |-- OpenInterestPoller.java
|   |   |-- LongShortRatioPoller.java
|   |   |-- LiquidationPoller.java
|   |   |-- ExchangeReservePoller.java
|   |   |-- BUILD
|   |-- onchain/
|   |   |-- StablecoinFlowPoller.java
|   |   |-- BtcDominancePoller.java
|   |   |-- BUILD
|   |-- BUILD
|-- storage/
|   |-- SentimentDataStore.java          # Redis-backed latest values
|   |-- SentimentInfluxWriter.java       # Historical tracking
|   |-- SentimentKafkaPublisher.java     # Kafka publishing
|   |-- BUILD
|-- backtesting/
|   |-- SentimentBacktester.java         # Forward return computation
|   |-- BacktestReport.java             # Validation report model
|   |-- BUILD
|-- config/
|   |-- SentimentConfig.java            # Configuration POJO
|   |-- SourceConfig.java               # Per-source configuration
|   |-- BUILD
|-- BUILD

src/test/java/com/verlumen/tradestream/sentiment/
|-- scoring/
|   |-- CompositeSentimentScorerTest.java
|   |-- ContrarianDetectorTest.java
|   |-- RegimeEnhancerTest.java
|   |-- BUILD
|-- pollers/
|   |-- crowd/
|   |   |-- FearGreedPollerTest.java
|   |   |-- BUILD
|   |-- structure/
|   |   |-- FundingRatePollerTest.java
|   |   |-- FundingRateNormalizerTest.java
|   |   |-- BUILD
|   |-- BUILD
|-- backtesting/
|   |-- SentimentBacktesterTest.java
|   |-- BUILD
|-- BUILD

protos/
|-- sentiment.proto                      # SentimentScore, ContrarianSignal protos
```

### Proto Definition

```protobuf
// protos/sentiment.proto
syntax = "proto3";

package com.verlumen.tradestream.sentiment;

option java_package = "com.verlumen.tradestream.sentiment";
option java_multiple_files = true;

import "google/protobuf/timestamp.proto";

message SentimentScore {
  string symbol = 1;
  google.protobuf.Timestamp timestamp = 2;
  double composite_score = 3;

  map<string, CategoryScore> category_scores = 4;

  ContrarianSignal contrarian_signal = 5;
  RegimeEnhancement regime_enhancement = 6;
  DataQuality data_quality = 7;
}

message CategoryScore {
  double score = 1;
  double weight = 2;
  double contribution = 3;
  map<string, ComponentScore> components = 4;
}

message ComponentScore {
  double raw_value = 1;
  double normalized_value = 2;
  int64 age_minutes = 3;
  bool stale = 4;
}

message ContrarianSignal {
  enum Type {
    UNKNOWN = 0;
    EXTREME_FEAR_BUY = 1;
    EXTREME_GREED_CAUTION = 2;
    SHORT_SQUEEZE_SETUP = 3;
    LONG_SQUEEZE_SETUP = 4;
  }
  Type type = 1;
  double intensity = 2;
  string reasoning = 3;
}

message RegimeEnhancement {
  string sentiment_regime = 1;
  string volatility_regime = 2;
  string combined_regime = 3;
}

message DataQuality {
  int32 sources_available = 1;
  int32 sources_stale = 2;
  int32 sources_missing = 3;
  double coverage_pct = 4;
}
```

## Implementing Issues

| Issue | Status | Description |
|-------|--------|-------------|
| #TBD  | open   | Implement SentimentPoller interface and PollerScheduler |
| #TBD  | open   | Implement Fear & Greed, Social Dominance, Google Trends pollers |
| #TBD  | open   | Implement funding rate, OI, long/short ratio pollers |
| #TBD  | open   | Implement liquidation, exchange reserve, stablecoin flow pollers |
| #TBD  | open   | Implement CompositeSentimentScorer with missing data handling |
| #TBD  | open   | Implement ContrarianDetector |
| #TBD  | open   | Implement RegimeEnhancer and integrate with existing regime detection |
| #TBD  | open   | Add sentiment.proto and build targets |
| #TBD  | open   | Integrate market_sentiment_score into opportunity scoring formula |
| #TBD  | open   | Implement SentimentBacktester and daily validation job |
| #TBD  | open   | Add Kafka publisher and InfluxDB writer |
| #TBD  | open   | Helm chart updates for sentiment service configuration |

## Notes

- **API Key Management**: LunarCrush, Santiment, CryptoQuant, and Glassnode require API keys. These are stored as Kubernetes secrets and injected via environment variables. The system should function with a subset of sources disabled if keys are unavailable.

- **Google Trends Reliability**: The unofficial pytrends library is prone to breaking. Implement via a Python sidecar service called from the Java poller. If Google Trends is unavailable, the system gracefully degrades (it is only 15% of crowd sentiment, which is 35% of composite = 5.25% of total score).

- **Funding Rate Aggregation**: Using median across exchanges rather than mean to avoid outlier exchanges skewing the result. If only one exchange is available, use that value directly.

- **Backtest Bootstrap Period**: The backtesting module requires 30+ days of historical sentiment data before generating meaningful reports. During the bootstrap period, contrarian adjustments are still applied based on pre-configured thresholds, but the model is not yet validated against live data.

- **Alternatives Considered**:
  - **ML-based sentiment model**: Rejected for v1. Raw indices with transparent weights are more explainable and debuggable. ML model can be layered on in v2 once sufficient backtest data exists.
  - **Single composite index (e.g., just Fear & Greed)**: Rejected. Too coarse and updates only daily. Market structure data provides much higher-frequency signal.
  - **Higher sentiment weight (>10%) in opportunity scoring**: Rejected for v1. Sentiment should supplement, not dominate, technical signals. Weight can be increased once backtesting validates the model.
