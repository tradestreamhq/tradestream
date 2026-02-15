# Influential Trader Tracking

## Goal

Track influential crypto traders across external social platforms (Twitter/X, YouTube, Telegram) and incorporate their public directional calls as a signal factor in TradeStream's opportunity scoring, enabling the platform to blend social intelligence with technical analysis.

## Target Behavior

The system maintains a curated registry of influential crypto traders, monitors their public posts in near-real-time, detects directional trading calls using NLP, tracks each influencer's historical accuracy, and produces an `influencer_consensus_score` (0-1) per symbol that feeds into opportunity scoring.

### End-to-End Flow

1. **Scrape**: Platform adapters poll public posts from registered influencers at configurable intervals
2. **Detect**: NLP classifier identifies directional calls and assigns detection confidence
3. **Record**: Detected calls are persisted with metadata for track record evaluation
4. **Score**: Track record engine recalculates influencer reliability after each call resolves
5. **Aggregate**: Consensus engine computes weighted agreement across reliable influencers per symbol
6. **Integrate**: `influencer_consensus_score` is published to Kafka for the Opportunity Scorer

### Architecture

```
+------------------------------------------------------------------+
|                  INFLUENCER TRACKING PIPELINE                     |
|                                                                   |
|  +-----------+   +-----------+   +-----------+                   |
|  | Twitter/X |   | YouTube   |   | Telegram  |                   |
|  | Adapter   |   | Adapter   |   | Adapter   |                   |
|  +-----+-----+   +-----+-----+   +-----+-----+                  |
|        |               |               |                          |
|        +-------+-------+-------+-------+                          |
|                |                                                  |
|                v                                                  |
|  +---------------------------+                                   |
|  | Kafka: influencer.raw     |                                   |
|  | (raw posts)               |                                   |
|  +-------------+-------------+                                   |
|                |                                                  |
|                v                                                  |
|  +---------------------------+    +---------------------------+  |
|  | Call Detection Service    |    | Influencer Registry       |  |
|  | (Beam/Flink pipeline)     |--->| (PostgreSQL)              |  |
|  |                           |    |                           |  |
|  | - NLP classification      |    | - profiles, accuracy      |  |
|  | - confidence scoring      |    | - domain expertise        |  |
|  | - symbol extraction       |    | - influence weight        |  |
|  +-------------+-------------+    +---------------------------+  |
|                |                              ^                   |
|                v                              |                   |
|  +---------------------------+                |                   |
|  | Kafka: influencer.calls   |                |                   |
|  | (detected calls)          |                |                   |
|  +-------------+-------------+                |                   |
|                |                              |                   |
|         +------+------+                       |                   |
|         |             |                       |                   |
|         v             v                       |                   |
|  +-----------+  +------------------+          |                   |
|  | Track     |  | Consensus        |          |                   |
|  | Record    |  | Engine           |          |                   |
|  | Scorer    |  |                  |          |                   |
|  |           +->| - weighted vote  |          |                   |
|  | - hit rate|  | - threshold calc |          |                   |
|  | - returns |  | - conflict detect|          |                   |
|  | - lead    |  +--------+---------+          |                   |
|  |   time    |           |                    |                   |
|  +-----+-----+           v                    |                   |
|        |       +-------------------+          |                   |
|        +------>| Kafka:            |          |                   |
|                | influencer.scores |          |                   |
|                +--------+----------+          |                   |
|                         |                     |                   |
|                         v                     |                   |
|                +-------------------+          |                   |
|                | Opportunity       |          |                   |
|                | Scorer Agent      |          |                   |
|                | (+influencer      |          |                   |
|                |  consensus score) |          |                   |
|                +-------------------+          |                   |
|                                               |                   |
|  +---------------------------+                |                   |
|  | Anti-Gaming Engine        |----------------+                   |
|  | - pump & dump detection   |                                   |
|  | - front-running detection |                                   |
|  | - reliability degradation |                                   |
|  +---------------------------+                                   |
+------------------------------------------------------------------+
```

## Data Sources

### Platform Adapters

| Platform | API/Method | Rate Limits | Data Available |
|----------|-----------|-------------|----------------|
| Twitter/X | Twitter API v2 (Basic tier) | 10,000 reads/month (Basic), 1M (Pro) | Tweets, replies, quote tweets, follower count |
| YouTube | YouTube Data API v3 | 10,000 units/day | Video titles, descriptions, comments, subscriber count |
| Telegram | Telegram Bot API + MTProto | No published limits (reasonable use) | Channel posts, group messages, member count |

### Data Contract: Raw Post

```protobuf
// protos/influencer.proto

syntax = "proto3";
package com.verlumn.tradestream.influencer;

import "google/protobuf/timestamp.proto";

message RawPost {
  string post_id = 1;              // Platform-specific unique ID
  string influencer_id = 2;        // Internal registry ID
  string platform = 3;             // TWITTER, YOUTUBE, TELEGRAM
  string content = 4;              // Full text content
  string url = 5;                  // Permalink
  int64 engagement_count = 6;      // Likes + retweets + replies
  int64 follower_count = 7;        // At time of post
  google.protobuf.Timestamp posted_at = 8;
  google.protobuf.Timestamp scraped_at = 9;
  map<string, string> metadata = 10; // Platform-specific fields
}
```

### Data Contract: Detected Call

```protobuf
message DetectedCall {
  string call_id = 1;
  string post_id = 2;
  string influencer_id = 3;
  string symbol = 4;               // e.g., "BTC/USD", "ETH/USD"
  Direction direction = 5;
  double detection_confidence = 6;  // 0.0 - 1.0
  string extracted_quote = 7;       // The exact phrase that triggered detection
  double price_at_call = 8;         // Market price when call was made
  google.protobuf.Timestamp call_time = 9;
  CallType call_type = 10;
  string target_price = 11;         // Optional: if influencer stated a target
  string stop_loss = 12;            // Optional: if stated
  string timeframe = 13;            // Optional: "short-term", "swing", "long-term"
}

enum Direction {
  DIRECTION_UNSPECIFIED = 0;
  BULLISH = 1;
  BEARISH = 2;
}

enum CallType {
  CALL_TYPE_UNSPECIFIED = 0;
  ENTRY = 1;          // Opening a position
  EXIT = 2;           // Closing a position
  ADD = 3;            // Adding to existing position
  REDUCE = 4;         // Reducing existing position
}
```

## Implementation

### 1. Influencer Registry

The registry is a curated PostgreSQL table seeded with an initial list of 50-100 top crypto influencers and maintained by admins.

#### Schema

```sql
-- V13: Influencer registry tables
CREATE TABLE influencer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(20) NOT NULL,          -- TWITTER, YOUTUBE, TELEGRAM
    handle VARCHAR(255) NOT NULL,           -- @handle or channel ID
    display_name VARCHAR(255) NOT NULL,
    follower_count BIGINT DEFAULT 0,
    domain_expertise VARCHAR(50)[] NOT NULL, -- {btc_maxi, altcoin, defi, macro, nft}
    influence_weight DOUBLE PRECISION DEFAULT 0.5,  -- 0.0 - 1.0
    reliability_score DOUBLE PRECISION DEFAULT 0.5, -- 0.0 - 1.0, updated by track record
    total_calls INT DEFAULT 0,
    correct_calls INT DEFAULT 0,
    avg_return_on_calls DOUBLE PRECISION DEFAULT 0.0,
    avg_lead_time_minutes INT DEFAULT 0,
    false_positive_rate DOUBLE PRECISION DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    is_flagged BOOLEAN DEFAULT FALSE,       -- Flagged by anti-gaming engine
    flag_reason VARCHAR(500),
    scrape_interval_seconds INT DEFAULT 300, -- Per-influencer poll rate
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, handle)
);

CREATE INDEX idx_influencer_platform ON influencer_profiles(platform);
CREATE INDEX idx_influencer_active ON influencer_profiles(is_active);
CREATE INDEX idx_influencer_reliability ON influencer_profiles(reliability_score DESC);
CREATE INDEX idx_influencer_domain ON influencer_profiles USING GIN(domain_expertise);

CREATE TABLE influencer_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    influencer_id UUID NOT NULL REFERENCES influencer_profiles(id),
    post_id VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,          -- BULLISH, BEARISH
    call_type VARCHAR(10) NOT NULL,          -- ENTRY, EXIT, ADD, REDUCE
    detection_confidence DOUBLE PRECISION NOT NULL,
    extracted_quote TEXT NOT NULL,
    price_at_call DOUBLE PRECISION NOT NULL,
    target_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    timeframe VARCHAR(20),                   -- short-term, swing, long-term
    resolved BOOLEAN DEFAULT FALSE,
    resolution_price DOUBLE PRECISION,
    resolution_return DOUBLE PRECISION,      -- Percentage return
    resolution_time TIMESTAMPTZ,
    is_correct BOOLEAN,                      -- NULL until resolved
    lead_time_minutes INT,                   -- Time between call and significant move
    call_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(influencer_id, post_id, symbol)
);

CREATE INDEX idx_calls_influencer ON influencer_calls(influencer_id);
CREATE INDEX idx_calls_symbol ON influencer_calls(symbol);
CREATE INDEX idx_calls_unresolved ON influencer_calls(resolved) WHERE resolved = FALSE;
CREATE INDEX idx_calls_time ON influencer_calls(call_time DESC);

CREATE TABLE influencer_consensus_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    consensus_score DOUBLE PRECISION NOT NULL,  -- 0.0 - 1.0
    bullish_count INT NOT NULL,
    bearish_count INT NOT NULL,
    total_influencers INT NOT NULL,
    weighted_bullish DOUBLE PRECISION NOT NULL,
    weighted_bearish DOUBLE PRECISION NOT NULL,
    top_bullish_influencers JSONB,           -- [{id, handle, reliability}]
    top_bearish_influencers JSONB,
    conflicts_with_ta BOOLEAN DEFAULT FALSE,
    ta_direction VARCHAR(10),                -- Current TA signal direction
    snapshot_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_consensus_symbol_time ON influencer_consensus_snapshots(symbol, snapshot_time DESC);
```

#### Seed Data Structure

```java
// src/main/java/com/verlumn/tradestream/influencer/InfluencerSeed.java

public final class InfluencerSeed {
    public record InfluencerEntry(
        String platform,
        String handle,
        String displayName,
        List<String> domainExpertise,
        double initialWeight
    ) {}

    public static final ImmutableList<InfluencerEntry> INITIAL_INFLUENCERS =
        ImmutableList.of(
            // Tier 1: High-influence, well-known analysts
            new InfluencerEntry("TWITTER", "PeterLBrandt", "Peter Brandt",
                List.of("btc_maxi", "macro"), 0.85),
            new InfluencerEntry("TWITTER", "CryptoCred", "Crypto Cred",
                List.of("altcoin", "defi"), 0.80),
            new InfluencerEntry("TWITTER", "CryptoCapo_", "Capo of Crypto",
                List.of("btc_maxi", "altcoin"), 0.75),
            new InfluencerEntry("TWITTER", "pentaboroshi", "Pentoshi",
                List.of("altcoin", "defi"), 0.80),
            new InfluencerEntry("TWITTER", "HsakaTrades", "Hsaka",
                List.of("altcoin", "defi"), 0.80),
            // ... 50-100 total entries across platforms
            // Tier 2: Medium influence
            // Tier 3: Niche specialists
            new InfluencerEntry("YOUTUBE", "UCRvqjQPYul8vSnZOqy7fUAg",
                "Benjamin Cowen", List.of("btc_maxi", "macro"), 0.85),
            new InfluencerEntry("TELEGRAM", "whale_alert_io", "Whale Alert",
                List.of("btc_maxi", "altcoin"), 0.70)
        );
}
```

### 2. Call Detection Service

The Call Detection Service is an Apache Beam pipeline running on Flink that consumes raw posts from Kafka and classifies them as directional trading calls.

#### NLP Classification Pipeline

```
+-------------------------------------------------------------+
|              CALL DETECTION BEAM PIPELINE                    |
|                                                              |
|  +------------------+                                       |
|  | Read from Kafka  |  influencer.raw                       |
|  | (RawPost)        |                                       |
|  +--------+---------+                                       |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Pre-filter       |  Drop retweets, replies, non-English  |
|  | (stateless)      |  Drop posts < 10 chars                |
|  +--------+---------+                                       |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Symbol Extractor |  Regex + alias map                    |
|  | (stateless)      |  "$BTC" -> "BTC/USD"                  |
|  +--------+---------+  "Bitcoin" -> "BTC/USD"               |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Call Classifier  |  LLM-based classification             |
|  | (stateless DoFn) |  Returns: call / commentary / noise   |
|  +--------+---------+                                       |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Confidence Gate  |  Drop if confidence < 0.60            |
|  | (stateless)      |                                       |
|  +--------+---------+                                       |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Enrich with      |  Add price_at_call from market data   |
|  | Market Data      |                                       |
|  +--------+---------+                                       |
|           |                                                  |
|           v                                                  |
|  +------------------+                                       |
|  | Write to Kafka   |  influencer.calls                     |
|  | (DetectedCall)   |                                       |
|  +------------------+                                       |
+-------------------------------------------------------------+
```

#### Call Classifier

The classifier uses a lightweight LLM to distinguish between actual directional calls and general commentary. This is implemented as a Beam DoFn to operate within the streaming pipeline.

```java
// src/main/java/com/verlumn/tradestream/influencer/CallClassifierDoFn.java

public final class CallClassifierDoFn extends DoFn<RawPost, DetectedCall> {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private static final String CLASSIFICATION_PROMPT = """
        Analyze this social media post from a crypto trader/analyst.
        Determine if it contains a directional trading call.

        Post: "%s"
        Author: %s (expertise: %s)

        Classify as one of:
        1. CALL - A directional trade recommendation (long/short/buy/sell)
        2. COMMENTARY - Market analysis without a clear directional call
        3. NOISE - Unrelated content, memes, personal posts

        If CALL, extract:
        - direction: BULLISH or BEARISH
        - symbol: The crypto asset (e.g., BTC, ETH, SOL)
        - call_type: ENTRY, EXIT, ADD, or REDUCE
        - confidence: 0.0-1.0 how certain you are this is a real call
        - extracted_quote: The exact phrase indicating the call
        - target_price: If mentioned (null otherwise)
        - timeframe: short-term (<1 day), swing (1-7 days), long-term (>7 days)

        Respond in JSON only.
        """;

    // Keyword pre-filter to avoid unnecessary LLM calls
    private static final ImmutableSet<String> CALL_KEYWORDS = ImmutableSet.of(
        "long", "short", "buy", "sell", "bullish", "bearish",
        "entry", "exit", "target", "stop loss", "tp", "sl",
        "accumulating", "dumping", "loading", "bidding",
        "going long", "going short", "opened a", "closed my",
        "im buying", "i'm buying", "im selling", "i'm selling"
    );

    @ProcessElement
    public void processElement(
            @Element RawPost post,
            OutputReceiver<DetectedCall> receiver) {
        // Quick keyword pre-filter to reduce LLM calls
        String lowerContent = post.getContent().toLowerCase();
        boolean hasCallKeyword = CALL_KEYWORDS.stream()
            .anyMatch(lowerContent::contains);

        if (!hasCallKeyword) {
            return; // Skip LLM call for obvious non-calls
        }

        try {
            ClassificationResult result = classifyWithLlm(post);

            if (result.classification() == Classification.CALL
                    && result.confidence() >= 0.60) {
                DetectedCall call = DetectedCall.newBuilder()
                    .setCallId(UUID.randomUUID().toString())
                    .setPostId(post.getPostId())
                    .setInfluencerId(post.getInfluencerId())
                    .setSymbol(normalizeSymbol(result.symbol()))
                    .setDirection(result.direction())
                    .setDetectionConfidence(result.confidence())
                    .setExtractedQuote(result.extractedQuote())
                    .setCallType(result.callType())
                    .setCallTime(post.getPostedAt())
                    .build();

                receiver.output(call);
            }
        } catch (Exception e) {
            logger.atWarning().withCause(e)
                .log("Failed to classify post %s", post.getPostId());
        }
    }

    private String normalizeSymbol(String raw) {
        // Map common aliases to canonical symbol format
        return SymbolAliasMap.normalize(raw);
    }
}
```

#### Symbol Alias Map

```java
// src/main/java/com/verlumn/tradestream/influencer/SymbolAliasMap.java

public final class SymbolAliasMap {
    private static final ImmutableMap<String, String> ALIASES = ImmutableMap.<String, String>builder()
        .put("btc", "BTC/USD").put("bitcoin", "BTC/USD").put("xbt", "BTC/USD")
        .put("eth", "ETH/USD").put("ethereum", "ETH/USD").put("ether", "ETH/USD")
        .put("sol", "SOL/USD").put("solana", "SOL/USD")
        .put("doge", "DOGE/USD").put("dogecoin", "DOGE/USD")
        .put("avax", "AVAX/USD").put("avalanche", "AVAX/USD")
        .put("matic", "MATIC/USD").put("polygon", "MATIC/USD")
        .put("link", "LINK/USD").put("chainlink", "LINK/USD")
        .put("uni", "UNI/USD").put("uniswap", "UNI/USD")
        .put("aave", "AAVE/USD")
        .put("snx", "SNX/USD").put("synthetix", "SNX/USD")
        .put("crv", "CRV/USD").put("curve", "CRV/USD")
        .put("comp", "COMP/USD").put("compound", "COMP/USD")
        .put("mkr", "MKR/USD").put("maker", "MKR/USD")
        .put("sushi", "SUSHI/USD").put("sushiswap", "SUSHI/USD")
        .put("yfi", "YFI/USD").put("yearn", "YFI/USD")
        .put("1inch", "1INCH/USD")
        .put("bal", "BAL/USD").put("balancer", "BAL/USD")
        .put("ldo", "LDO/USD").put("lido", "LDO/USD")
        .put("rpl", "RPL/USD").put("rocketpool", "RPL/USD")
        .put("fxs", "FXS/USD").put("frax", "FXS/USD")
        .buildOrThrow();

    // Regex for common patterns: $BTC, #BTC, BTC/USD, BTCUSD
    private static final Pattern SYMBOL_PATTERN = Pattern.compile(
        "[$#]?([A-Z]{2,10})(?:/USD|USDT?)?",
        Pattern.CASE_INSENSITIVE
    );

    public static String normalize(String raw) {
        String lower = raw.toLowerCase().trim().replaceAll("[$#]", "");
        if (ALIASES.containsKey(lower)) {
            return ALIASES.get(lower);
        }
        // Fallback: assume it's a ticker, append /USD
        return raw.toUpperCase() + "/USD";
    }

    public static ImmutableList<String> extractSymbols(String text) {
        ImmutableList.Builder<String> symbols = ImmutableList.builder();
        Matcher matcher = SYMBOL_PATTERN.matcher(text);
        while (matcher.find()) {
            String candidate = matcher.group(1).toLowerCase();
            if (ALIASES.containsKey(candidate)) {
                symbols.add(ALIASES.get(candidate));
            }
        }
        return symbols.build();
    }
}
```

### 3. Track Record Scoring

The track record engine evaluates each influencer's historical accuracy by resolving past calls against actual price movements.

#### Resolution Logic

```java
// src/main/java/com/verlumn/tradestream/influencer/TrackRecordScorer.java

public final class TrackRecordScorer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    // Resolution windows by timeframe
    private static final ImmutableMap<String, Duration> RESOLUTION_WINDOWS =
        ImmutableMap.of(
            "short-term", Duration.ofHours(24),
            "swing", Duration.ofDays(7),
            "long-term", Duration.ofDays(30)
        );

    // Default resolution window if timeframe not specified
    private static final Duration DEFAULT_WINDOW = Duration.ofDays(3);

    // Minimum price move to consider a call "correct"
    private static final double MIN_MOVE_THRESHOLD = 0.02; // 2%

    /**
     * Resolve unresolved calls that have passed their resolution window.
     * Called periodically (every 15 minutes) by a scheduled job.
     */
    public ImmutableList<ResolvedCall> resolveExpiredCalls(
            List<InfluencerCall> unresolvedCalls,
            MarketDataClient marketData) {
        ImmutableList.Builder<ResolvedCall> resolved = ImmutableList.builder();

        for (InfluencerCall call : unresolvedCalls) {
            Duration window = RESOLUTION_WINDOWS.getOrDefault(
                call.getTimeframe(), DEFAULT_WINDOW);

            Instant resolutionTime = call.getCallTime().plus(window);

            if (Instant.now().isAfter(resolutionTime)) {
                double resolutionPrice = marketData.getPriceAt(
                    call.getSymbol(), resolutionTime);

                double returnPct = (resolutionPrice - call.getPriceAtCall())
                    / call.getPriceAtCall();

                boolean isCorrect = evaluateCall(call, returnPct);

                // Calculate lead time: when did the move actually start?
                int leadTimeMinutes = calculateLeadTime(
                    call, marketData);

                resolved.add(ResolvedCall.builder()
                    .callId(call.getId())
                    .resolutionPrice(resolutionPrice)
                    .resolutionReturn(returnPct)
                    .isCorrect(isCorrect)
                    .leadTimeMinutes(leadTimeMinutes)
                    .resolutionTime(resolutionTime)
                    .build());
            }
        }

        return resolved.build();
    }

    private boolean evaluateCall(InfluencerCall call, double returnPct) {
        if (call.getDirection().equals("BULLISH")) {
            // Bullish call is correct if price moved up by at least threshold
            return returnPct >= MIN_MOVE_THRESHOLD;
        } else {
            // Bearish call is correct if price moved down by at least threshold
            return returnPct <= -MIN_MOVE_THRESHOLD;
        }
    }

    /**
     * Calculate lead time: minutes between the call and when the
     * significant price move began. Lower lead time = influencer
     * may be front-running rather than predicting.
     */
    private int calculateLeadTime(
            InfluencerCall call,
            MarketDataClient marketData) {
        List<Candle> candles = marketData.getCandles(
            call.getSymbol(), "5m",
            call.getCallTime(),
            call.getCallTime().plus(Duration.ofHours(24)));

        double threshold = call.getPriceAtCall() * MIN_MOVE_THRESHOLD;
        double cumReturn = 0;

        for (Candle candle : candles) {
            cumReturn += (candle.getClose() - candle.getOpen());
            if (Math.abs(cumReturn) >= threshold) {
                return (int) Duration.between(
                    call.getCallTime(),
                    candle.getTimestamp()).toMinutes();
            }
        }

        return -1; // No significant move detected
    }

    /**
     * Update an influencer's reliability score based on their
     * complete call history.
     */
    public ReliabilityScore calculateReliability(
            InfluencerProfile profile,
            List<InfluencerCall> resolvedCalls) {
        if (resolvedCalls.isEmpty()) {
            return ReliabilityScore.defaultScore();
        }

        // Hit rate: correct calls / total resolved calls
        long correct = resolvedCalls.stream()
            .filter(InfluencerCall::getIsCorrect)
            .count();
        double hitRate = (double) correct / resolvedCalls.size();

        // Average return when following calls
        double avgReturn = resolvedCalls.stream()
            .filter(InfluencerCall::getIsCorrect)
            .mapToDouble(InfluencerCall::getResolutionReturn)
            .average()
            .orElse(0.0);

        // Average lead time (minutes)
        double avgLeadTime = resolvedCalls.stream()
            .filter(c -> c.getLeadTimeMinutes() > 0)
            .mapToInt(InfluencerCall::getLeadTimeMinutes)
            .average()
            .orElse(0.0);

        // False positive rate: calls that went against predicted direction
        long falsePositives = resolvedCalls.stream()
            .filter(c -> !c.getIsCorrect())
            .count();
        double fpRate = (double) falsePositives / resolvedCalls.size();

        // Recency weighting: more recent calls matter more
        double recencyWeightedHitRate = calculateRecencyWeightedHitRate(
            resolvedCalls);

        // Composite reliability score
        // 50% hit rate + 20% avg return quality + 15% consistency + 15% recency
        double returnQuality = Math.min(avgReturn / 0.10, 1.0); // 10% = perfect
        double consistency = 1.0 - calculateReturnStdDev(resolvedCalls);

        double reliability = 0.50 * recencyWeightedHitRate
            + 0.20 * returnQuality
            + 0.15 * Math.max(0, consistency)
            + 0.15 * (1.0 - fpRate);

        return ReliabilityScore.builder()
            .score(Math.max(0.0, Math.min(1.0, reliability)))
            .hitRate(hitRate)
            .avgReturn(avgReturn)
            .avgLeadTimeMinutes((int) avgLeadTime)
            .falsePositiveRate(fpRate)
            .totalCalls(resolvedCalls.size())
            .correctCalls((int) correct)
            .build();
    }

    /**
     * Weight recent calls more heavily using exponential decay.
     * Half-life of 30 days: calls from 30 days ago have 50% weight.
     */
    private double calculateRecencyWeightedHitRate(
            List<InfluencerCall> resolvedCalls) {
        double halfLifeDays = 30.0;
        double decayRate = Math.log(2) / halfLifeDays;

        double weightedCorrect = 0;
        double totalWeight = 0;

        Instant now = Instant.now();
        for (InfluencerCall call : resolvedCalls) {
            double daysAgo = Duration.between(
                call.getCallTime(), now).toDays();
            double weight = Math.exp(-decayRate * daysAgo);

            totalWeight += weight;
            if (call.getIsCorrect()) {
                weightedCorrect += weight;
            }
        }

        return totalWeight > 0 ? weightedCorrect / totalWeight : 0.5;
    }

    private double calculateReturnStdDev(List<InfluencerCall> calls) {
        double[] returns = calls.stream()
            .mapToDouble(InfluencerCall::getResolutionReturn)
            .toArray();
        if (returns.length < 2) return 0.5;

        double mean = Arrays.stream(returns).average().orElse(0);
        double variance = Arrays.stream(returns)
            .map(r -> Math.pow(r - mean, 2))
            .average()
            .orElse(0);
        return Math.sqrt(variance);
    }
}
```

### 4. Influencer Consensus Engine

When multiple reliable influencers agree on a direction for a given symbol, the consensus signal is stronger.

```java
// src/main/java/com/verlumn/tradestream/influencer/ConsensusEngine.java

public final class ConsensusEngine {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final ConsensusConfig config;

    @Inject
    public ConsensusEngine(ConsensusConfig config) {
        this.config = config;
    }

    /**
     * Calculate influencer consensus score for a symbol.
     *
     * @param activeCalls Recent calls (within lookback window) for a symbol
     * @param profiles    Influencer profiles with reliability scores
     * @return ConsensusResult with score 0.0 - 1.0
     */
    public ConsensusResult calculateConsensus(
            String symbol,
            List<DetectedCall> activeCalls,
            Map<String, InfluencerProfile> profiles) {

        // Filter to calls from influencers meeting minimum reliability
        List<WeightedCall> qualifiedCalls = activeCalls.stream()
            .filter(call -> {
                InfluencerProfile profile = profiles.get(call.getInfluencerId());
                return profile != null
                    && profile.getReliabilityScore() >= config.getMinReliability()
                    && !profile.getIsFlagged();
            })
            .map(call -> {
                InfluencerProfile profile = profiles.get(call.getInfluencerId());
                double weight = calculateCallWeight(call, profile);
                return new WeightedCall(call, profile, weight);
            })
            .toList();

        if (qualifiedCalls.isEmpty()) {
            return ConsensusResult.neutral(symbol);
        }

        // Weighted vote tallying
        double bullishWeight = 0;
        double bearishWeight = 0;
        int bullishCount = 0;
        int bearishCount = 0;

        for (WeightedCall wc : qualifiedCalls) {
            if (wc.call().getDirection() == Direction.BULLISH) {
                bullishWeight += wc.weight();
                bullishCount++;
            } else if (wc.call().getDirection() == Direction.BEARISH) {
                bearishWeight += wc.weight();
                bearishCount++;
            }
        }

        double totalWeight = bullishWeight + bearishWeight;
        if (totalWeight == 0) {
            return ConsensusResult.neutral(symbol);
        }

        // Consensus score: how strongly do influencers agree?
        // 1.0 = all influencers agree on one direction
        // 0.5 = evenly split
        // 0.0 = no active calls
        double majorityWeight = Math.max(bullishWeight, bearishWeight);
        double rawConsensus = majorityWeight / totalWeight;

        // Apply minimum participation threshold
        int totalInfluencers = bullishCount + bearishCount;
        double participationFactor = Math.min(
            (double) totalInfluencers / config.getMinParticipants(),
            1.0
        );

        // Final consensus score, scaled by participation
        double consensusScore = rawConsensus * participationFactor;

        // Determine consensus direction
        Direction consensusDirection = bullishWeight >= bearishWeight
            ? Direction.BULLISH : Direction.BEARISH;

        return ConsensusResult.builder()
            .symbol(symbol)
            .consensusScore(Math.min(1.0, consensusScore))
            .direction(consensusDirection)
            .bullishCount(bullishCount)
            .bearishCount(bearishCount)
            .totalInfluencers(totalInfluencers)
            .weightedBullish(bullishWeight)
            .weightedBearish(bearishWeight)
            .topBullishInfluencers(getTopInfluencers(qualifiedCalls, Direction.BULLISH, 3))
            .topBearishInfluencers(getTopInfluencers(qualifiedCalls, Direction.BEARISH, 3))
            .build();
    }

    /**
     * Calculate weight for a single call based on:
     * - Influencer reliability score (50%)
     * - Influence weight / follower tier (25%)
     * - Detection confidence (15%)
     * - Recency of call (10%)
     */
    private double calculateCallWeight(
            DetectedCall call, InfluencerProfile profile) {
        double reliability = profile.getReliabilityScore();
        double influence = profile.getInfluenceWeight();
        double detection = call.getDetectionConfidence();
        double recency = calculateRecencyFactor(call.getCallTime());

        return 0.50 * reliability
            + 0.25 * influence
            + 0.15 * detection
            + 0.10 * recency;
    }

    /**
     * Recency factor: calls from the last hour get full weight,
     * decaying to 0 at the lookback window boundary.
     */
    private double calculateRecencyFactor(Instant callTime) {
        long minutesAgo = Duration.between(callTime, Instant.now()).toMinutes();
        long windowMinutes = config.getLookbackWindow().toMinutes();
        return Math.max(0, 1.0 - ((double) minutesAgo / windowMinutes));
    }

    private List<InfluencerSummary> getTopInfluencers(
            List<WeightedCall> calls,
            Direction direction,
            int limit) {
        return calls.stream()
            .filter(wc -> wc.call().getDirection() == direction)
            .sorted(Comparator.comparingDouble(WeightedCall::weight).reversed())
            .limit(limit)
            .map(wc -> new InfluencerSummary(
                wc.profile().getId(),
                wc.profile().getHandle(),
                wc.profile().getReliabilityScore()))
            .toList();
    }
}
```

#### Consensus Thresholds

| Condition | Threshold | Signal Strength |
|-----------|-----------|-----------------|
| Strong consensus | >= 70% weighted agreement, >= 3 participants | `consensus_score` > 0.70 |
| Moderate consensus | >= 55% weighted agreement, >= 2 participants | `consensus_score` 0.50 - 0.70 |
| Weak / no consensus | < 55% agreement or < 2 participants | `consensus_score` < 0.50 |
| Conflicting (split) | 45-55% split with >= 4 participants | Flags `conflicts_detected: true` |

## Integration with Opportunity Scoring

### Updated Scoring Formula

The `influencer_consensus_score` is added as an optional signal factor. When influencer data is available, the weights are redistributed:

```python
# Without influencer data (current behavior, unchanged)
WEIGHTS_BASE = {
    "confidence": 0.25,
    "expected_return": 0.30,
    "consensus": 0.20,       # Strategy consensus
    "volatility": 0.15,
    "freshness": 0.10,
}

# With influencer data available
WEIGHTS_WITH_INFLUENCER = {
    "confidence": 0.22,
    "expected_return": 0.27,
    "consensus": 0.18,       # Strategy consensus (slightly reduced)
    "volatility": 0.13,
    "freshness": 0.08,
    "influencer_consensus": 0.12,  # New: influencer signal
}

def calculate_opportunity_score_v2(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    market_regime: str = "normal",
    influencer_consensus: Optional[InfluencerConsensus] = None,
) -> float:
    """
    Calculate opportunity score with optional influencer consensus factor.

    When influencer consensus data is available, it receives 12% weight
    redistributed from existing factors. When unavailable, the original
    weights apply unchanged.
    """
    caps = get_regime_adjusted_caps(market_regime)
    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)
    volatility_score = min(volatility / caps.max_volatility, 1.0)
    freshness_score = max(0, 1 - (minutes_ago / 60))

    if influencer_consensus is not None and influencer_consensus.total_influencers >= 2:
        weights = WEIGHTS_WITH_INFLUENCER
        influencer_score = influencer_consensus.consensus_score

        # Bonus: if influencer consensus direction matches TA direction,
        # apply a confirmation multiplier
        if influencer_consensus.confirms_ta:
            influencer_score = min(1.0, influencer_score * 1.15)

        # Penalty: if influencer consensus conflicts with TA direction,
        # reduce the influencer contribution
        if influencer_consensus.conflicts_with_ta:
            influencer_score *= 0.50

        opportunity_score = (
            weights["confidence"] * confidence +
            weights["expected_return"] * return_score +
            weights["consensus"] * consensus_pct +
            weights["volatility"] * volatility_score +
            weights["freshness"] * freshness_score +
            weights["influencer_consensus"] * influencer_score
        ) * 100
    else:
        weights = WEIGHTS_BASE
        opportunity_score = (
            weights["confidence"] * confidence +
            weights["expected_return"] * return_score +
            weights["consensus"] * consensus_pct +
            weights["volatility"] * volatility_score +
            weights["freshness"] * freshness_score
        ) * 100

    return round(opportunity_score, 1)
```

### TA Confirmation / Conflict Detection

```java
// src/main/java/com/verlumn/tradestream/influencer/TaConflictDetector.java

public final class TaConflictDetector {

    /**
     * Compare influencer consensus direction with TA signal direction.
     *
     * @param consensus   The influencer consensus result
     * @param taSignal    The latest TA-based signal for the same symbol
     * @return Relationship between influencer and TA signals
     */
    public SignalRelationship detectRelationship(
            ConsensusResult consensus,
            Signal taSignal) {
        if (consensus.getConsensusScore() < 0.50) {
            // Weak consensus, no meaningful comparison
            return SignalRelationship.NEUTRAL;
        }

        boolean taIsBullish = taSignal.getAction().equals("BUY");
        boolean influencerIsBullish =
            consensus.getDirection() == Direction.BULLISH;

        if (taIsBullish == influencerIsBullish) {
            return SignalRelationship.CONFIRMS;
        } else {
            return SignalRelationship.CONFLICTS;
        }
    }

    public enum SignalRelationship {
        CONFIRMS,    // Both agree on direction
        CONFLICTS,   // Disagree on direction
        NEUTRAL      // Insufficient data to compare
    }
}
```

### Scored Signal Extension

The existing scored signal JSON is extended with an optional influencer section:

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
    "freshness": { "value": 0, "contribution": 8.0 },
    "influencer_consensus": {
      "value": 0.85,
      "contribution": 11.7,
      "direction": "BULLISH",
      "confirms_ta": true,
      "confirmation_bonus_applied": true,
      "influencer_count": 5,
      "top_influencers": [
        { "handle": "@PeterLBrandt", "reliability": 0.88 },
        { "handle": "@pentaboroshi", "reliability": 0.82 },
        { "handle": "@HsakaTrades", "reliability": 0.79 }
      ]
    }
  }
}
```

## Anti-Gaming Engine

The anti-gaming engine protects signal integrity by detecting influencers who may be manipulating markets (pump and dump schemes, front-running) and automatically degrading their reliability scores.

### Detection Patterns

```java
// src/main/java/com/verlumn/tradestream/influencer/AntiGamingEngine.java

public final class AntiGamingEngine {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final AntiGamingConfig config;

    @Inject
    public AntiGamingEngine(AntiGamingConfig config) {
        this.config = config;
    }

    /**
     * Analyze an influencer's recent behavior for gaming patterns.
     * Called after each call resolution and periodically for all active influencers.
     */
    public GamingAnalysis analyzeInfluencer(
            InfluencerProfile profile,
            List<InfluencerCall> recentCalls,
            MarketDataClient marketData) {

        ImmutableList.Builder<GamingFlag> flags = ImmutableList.builder();

        // Pattern 1: Pump and dump detection
        GamingFlag pumpDump = detectPumpAndDump(profile, recentCalls, marketData);
        if (pumpDump != null) flags.add(pumpDump);

        // Pattern 2: Front-running detection
        GamingFlag frontRunning = detectFrontRunning(profile, recentCalls, marketData);
        if (frontRunning != null) flags.add(frontRunning);

        // Pattern 3: Rapid flip-flopping
        GamingFlag flipFlop = detectFlipFlopping(profile, recentCalls);
        if (flipFlop != null) flags.add(flipFlop);

        // Pattern 4: Suspiciously correlated timing with price spikes
        GamingFlag spikeCorrelation = detectSpikeCorrelation(
            profile, recentCalls, marketData);
        if (spikeCorrelation != null) flags.add(spikeCorrelation);

        ImmutableList<GamingFlag> allFlags = flags.build();

        // Calculate degradation
        double degradation = allFlags.stream()
            .mapToDouble(GamingFlag::severity)
            .sum();

        return GamingAnalysis.builder()
            .influencerId(profile.getId())
            .flags(allFlags)
            .totalDegradation(Math.min(degradation, 0.80)) // Max 80% degradation
            .shouldFlag(degradation >= config.getFlagThreshold())
            .build();
    }

    /**
     * Pattern 1: Pump and dump detection.
     *
     * Indicators:
     * - Bullish call on low-cap asset followed by price spike and rapid reversal
     * - High engagement post (amplified reach) on illiquid assets
     * - Subsequent bearish call or silence after the dump
     */
    private GamingFlag detectPumpAndDump(
            InfluencerProfile profile,
            List<InfluencerCall> calls,
            MarketDataClient marketData) {

        for (InfluencerCall call : calls) {
            if (call.getDirection().equals("BEARISH")) continue;

            // Check for price spike within 2 hours of bullish call
            List<Candle> postCallCandles = marketData.getCandles(
                call.getSymbol(), "5m",
                call.getCallTime(),
                call.getCallTime().plus(Duration.ofHours(2)));

            double maxPrice = postCallCandles.stream()
                .mapToDouble(Candle::getHigh)
                .max()
                .orElse(call.getPriceAtCall());

            double spike = (maxPrice - call.getPriceAtCall()) / call.getPriceAtCall();

            // Check for reversal after spike
            List<Candle> afterSpike = marketData.getCandles(
                call.getSymbol(), "5m",
                call.getCallTime().plus(Duration.ofHours(2)),
                call.getCallTime().plus(Duration.ofHours(6)));

            double postSpikePrice = afterSpike.isEmpty()
                ? maxPrice
                : afterSpike.get(afterSpike.size() - 1).getClose();

            double reversal = (maxPrice - postSpikePrice) / maxPrice;

            // Pump and dump pattern: spike > 10% followed by reversal > 70% of spike
            if (spike > 0.10 && reversal > spike * 0.70) {
                return GamingFlag.builder()
                    .pattern("PUMP_AND_DUMP")
                    .severity(0.40)
                    .evidence(String.format(
                        "Spike of %.1f%% within 2h of bullish call, "
                        + "followed by %.1f%% reversal. Symbol: %s",
                        spike * 100, reversal * 100, call.getSymbol()))
                    .callId(call.getId())
                    .build();
            }
        }

        return null;
    }

    /**
     * Pattern 2: Front-running detection.
     *
     * Indicators:
     * - Influencer consistently calls AFTER on-chain activity shows large buys
     * - Very short lead times (< 5 minutes) between price move start and call
     * - Price already moved significantly before call was posted
     */
    private GamingFlag detectFrontRunning(
            InfluencerProfile profile,
            List<InfluencerCall> calls,
            MarketDataClient marketData) {

        long suspiciousCalls = calls.stream()
            .filter(call -> {
                // Check price action in the 30 min BEFORE the call
                List<Candle> preCallCandles = marketData.getCandles(
                    call.getSymbol(), "5m",
                    call.getCallTime().minus(Duration.ofMinutes(30)),
                    call.getCallTime());

                if (preCallCandles.isEmpty()) return false;

                double preMoveStart = preCallCandles.get(0).getOpen();
                double preMoveEnd = preCallCandles.get(
                    preCallCandles.size() - 1).getClose();
                double preCallMove = (preMoveEnd - preMoveStart) / preMoveStart;

                // If price already moved > 3% in call direction before post
                if (call.getDirection().equals("BULLISH") && preCallMove > 0.03) {
                    return true;
                }
                if (call.getDirection().equals("BEARISH") && preCallMove < -0.03) {
                    return true;
                }

                return false;
            })
            .count();

        // If > 50% of calls show front-running pattern
        double frontRunRate = (double) suspiciousCalls / calls.size();
        if (frontRunRate > 0.50 && calls.size() >= 5) {
            return GamingFlag.builder()
                .pattern("FRONT_RUNNING")
                .severity(0.30)
                .evidence(String.format(
                    "%.0f%% of calls (%d/%d) show significant price movement "
                    + "in the call direction before the post was made",
                    frontRunRate * 100, suspiciousCalls, calls.size()))
                .build();
        }

        return null;
    }

    /**
     * Pattern 3: Rapid flip-flopping.
     *
     * Indicators:
     * - Bullish call followed by bearish call on same symbol within 4 hours
     * - Frequent direction changes without clear market catalysts
     */
    private GamingFlag detectFlipFlopping(
            InfluencerProfile profile,
            List<InfluencerCall> calls) {

        // Group by symbol and check for rapid direction changes
        Map<String, List<InfluencerCall>> bySymbol = calls.stream()
            .collect(Collectors.groupingBy(InfluencerCall::getSymbol));

        int flipFlops = 0;
        for (var entry : bySymbol.entrySet()) {
            List<InfluencerCall> symbolCalls = entry.getValue().stream()
                .sorted(Comparator.comparing(InfluencerCall::getCallTime))
                .toList();

            for (int i = 1; i < symbolCalls.size(); i++) {
                InfluencerCall prev = symbolCalls.get(i - 1);
                InfluencerCall curr = symbolCalls.get(i);

                Duration gap = Duration.between(
                    prev.getCallTime(), curr.getCallTime());

                if (!prev.getDirection().equals(curr.getDirection())
                        && gap.toHours() < 4) {
                    flipFlops++;
                }
            }
        }

        if (flipFlops >= 3) {
            return GamingFlag.builder()
                .pattern("FLIP_FLOPPING")
                .severity(0.20)
                .evidence(String.format(
                    "%d rapid direction changes within 4-hour windows "
                    + "in the last 30 days", flipFlops))
                .build();
        }

        return null;
    }

    /**
     * Pattern 4: Suspicious correlation with price spikes.
     *
     * Detects if an influencer's posts consistently precede
     * thin-market volume spikes, suggesting coordinated action.
     */
    private GamingFlag detectSpikeCorrelation(
            InfluencerProfile profile,
            List<InfluencerCall> calls,
            MarketDataClient marketData) {

        long spikedCalls = calls.stream()
            .filter(call -> {
                // Check volume in the 15 min after the call
                List<Candle> postCallCandles = marketData.getCandles(
                    call.getSymbol(), "5m",
                    call.getCallTime(),
                    call.getCallTime().plus(Duration.ofMinutes(15)));

                if (postCallCandles.size() < 3) return false;

                double avgVolume = postCallCandles.stream()
                    .mapToDouble(Candle::getVolume)
                    .average()
                    .orElse(0);

                // Get baseline volume for comparison
                List<Candle> baselineCandles = marketData.getCandles(
                    call.getSymbol(), "5m",
                    call.getCallTime().minus(Duration.ofHours(2)),
                    call.getCallTime());

                double baselineVolume = baselineCandles.stream()
                    .mapToDouble(Candle::getVolume)
                    .average()
                    .orElse(1);

                // Volume spike > 5x baseline within 15 min of post
                return avgVolume > baselineVolume * 5.0;
            })
            .count();

        double spikeRate = (double) spikedCalls / calls.size();
        if (spikeRate > 0.40 && calls.size() >= 5) {
            return GamingFlag.builder()
                .pattern("VOLUME_SPIKE_CORRELATION")
                .severity(0.25)
                .evidence(String.format(
                    "%.0f%% of calls followed by >5x volume spikes "
                    + "within 15 minutes", spikeRate * 100))
                .build();
        }

        return null;
    }

    /**
     * Apply degradation to an influencer's reliability score.
     * Called when gaming analysis detects suspicious patterns.
     */
    public double applyDegradation(
            InfluencerProfile profile,
            GamingAnalysis analysis) {
        double currentReliability = profile.getReliabilityScore();
        double newReliability = currentReliability * (1.0 - analysis.getTotalDegradation());

        logger.atWarning().log(
            "Degrading influencer %s (%s) reliability: %.2f -> %.2f. "
            + "Flags: %s",
            profile.getHandle(),
            profile.getPlatform(),
            currentReliability,
            newReliability,
            analysis.getFlags().stream()
                .map(GamingFlag::pattern)
                .collect(Collectors.joining(", ")));

        return Math.max(0.0, newReliability);
    }
}
```

### Anti-Gaming Configuration

```yaml
anti_gaming:
  scan_interval_minutes: 60          # Run analysis every hour
  lookback_days: 30                  # Analyze last 30 days of calls
  flag_threshold: 0.30               # Total degradation >= 30% triggers flag
  max_degradation: 0.80              # Maximum reliability reduction per scan
  auto_deactivate_threshold: 0.10    # Auto-deactivate if reliability drops below 10%
  recovery:
    enabled: true
    recovery_period_days: 90         # Clean behavior for 90 days restores score
    max_recovery_per_period: 0.20    # Max 20% reliability recovery per period
  patterns:
    pump_and_dump:
      spike_threshold: 0.10          # 10% price spike
      reversal_threshold: 0.70       # 70% reversal of spike
      window_hours: 6
      severity: 0.40
    front_running:
      pre_call_move_threshold: 0.03  # 3% pre-call price movement
      min_calls_for_detection: 5
      rate_threshold: 0.50           # 50% of calls show pattern
      severity: 0.30
    flip_flopping:
      window_hours: 4
      min_flips: 3
      severity: 0.20
    volume_spike:
      spike_multiplier: 5.0          # 5x baseline volume
      window_minutes: 15
      rate_threshold: 0.40
      severity: 0.25
```

## Configuration

### Service Configuration

```yaml
influencer_tracking:
  # Registry
  registry:
    min_follower_count: 10000        # Minimum followers for consideration
    min_reliability_for_consensus: 0.40
    initial_reliability: 0.50
    max_influencers: 500

  # Scraping
  scraping:
    twitter:
      api_tier: "basic"              # basic or pro
      poll_interval_seconds: 300     # 5 minutes
      max_tweets_per_poll: 100
      bearer_token: "${TWITTER_BEARER_TOKEN}"
    youtube:
      poll_interval_seconds: 900     # 15 minutes
      max_videos_per_poll: 10
      api_key: "${YOUTUBE_API_KEY}"
    telegram:
      poll_interval_seconds: 60      # 1 minute
      bot_token: "${TELEGRAM_BOT_TOKEN}"
    rate_limiting:
      global_max_requests_per_minute: 100
      per_platform_max_requests_per_minute: 50
      backoff_on_429: true
      max_backoff_seconds: 300

  # Call detection
  call_detection:
    model: "google/gemini-2.0-flash"   # Fast, cheap model for classification
    min_confidence: 0.60
    keyword_prefilter: true
    max_content_length: 2000           # Truncate longer posts
    batch_size: 10                     # Classify in batches for efficiency

  # Track record
  track_record:
    resolution_check_interval_minutes: 15
    min_move_threshold: 0.02           # 2% minimum price move
    resolution_windows:
      short_term_hours: 24
      swing_days: 7
      long_term_days: 30
    default_resolution_days: 3
    recency_half_life_days: 30

  # Consensus
  consensus:
    lookback_window_hours: 24          # Consider calls from last 24h
    min_participants: 2                # Minimum influencers for consensus
    min_reliability: 0.40              # Minimum reliability for participation
    strong_threshold: 0.70             # >= 70% = strong consensus
    moderate_threshold: 0.55           # >= 55% = moderate consensus
    publish_interval_seconds: 60       # Recalculate every minute

  # Integration
  integration:
    weight_with_influencer_data: 0.12  # 12% weight in opportunity scoring
    ta_confirmation_bonus: 0.15        # 15% bonus when confirms TA
    ta_conflict_penalty: 0.50          # 50% penalty when conflicts with TA
    kafka_topic_raw: "influencer.raw"
    kafka_topic_calls: "influencer.calls"
    kafka_topic_scores: "influencer.scores"
    redis_cache_prefix: "influencer:"
    redis_consensus_ttl_seconds: 120

  # Anti-gaming (see anti_gaming section above)
```

### Helm Values

```yaml
# charts/tradestream/values.yaml (additions)
influencerTracking:
  enabled: true
  scraper:
    replicas: 1
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "250m"
  callDetection:
    replicas: 1
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"
  trackRecord:
    replicas: 1
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "250m"
  consensus:
    replicas: 1
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "250m"
  secrets:
    twitterBearerToken: ""
    youtubeApiKey: ""
    telegramBotToken: ""
```

## Privacy and Legal Considerations

### Data Scraping Legality

| Principle | Approach |
|-----------|----------|
| Public data only | Only scrape publicly available posts; no private DMs, locked accounts, or subscriber-only content |
| API-first | Use official platform APIs (Twitter API v2, YouTube Data API, Telegram Bot API) wherever available |
| Terms of service | Comply with each platform's ToS and developer agreements |
| Rate limit compliance | Respect all published rate limits with built-in backoff |
| No impersonation | Bot accounts clearly identified as bots where required by platform rules |
| Robots.txt | Respect robots.txt for any web scraping fallback |

### GDPR Considerations

| Requirement | Implementation |
|-------------|----------------|
| Lawful basis | Legitimate interest: tracking publicly-expressed market opinions of public figures |
| Data minimization | Store only post content, handle, and engagement metrics; no personal data beyond public profiles |
| Right to erasure | Influencers can request removal from registry via support; automated within 72 hours |
| Data retention | Raw posts purged after 90 days; aggregated scores retained indefinitely |
| Transparency | Public documentation of which influencers are tracked and methodology |
| DPA | Data Processing Agreement with any third-party API providers |

### Ethical Use

- **No manipulation**: TradeStream does not interact with, reply to, or amplify influencer posts
- **Attribution**: When displaying influencer consensus in UI, attribute with "Based on public posts by tracked analysts"
- **Opt-out**: Any influencer can request removal from tracking
- **No PII beyond public profiles**: We do not track personal information, locations, or private accounts
- **Disclosure**: Platform documentation clearly states that influencer tracking is used as one of multiple signal factors

## Constraints

- Call detection pipeline must process posts within 60 seconds of scraping
- Consensus recalculation must complete in < 5 seconds for all active symbols
- Maximum 500 tracked influencers to bound scraping costs and LLM classification costs
- Track record resolution runs every 15 minutes (not real-time)
- Influencer data is additive: the system must function identically without any influencer data (graceful degradation)
- All scraping must use official platform APIs; no browser automation or unofficial API endpoints
- LLM classification costs must stay under $50/month at 500 influencers polling 5-minute intervals
- Anti-gaming scans must not block the main consensus pipeline

## Non-Goals

- **Automated trading based solely on influencer calls**: Influencer data is one signal factor among many, never a standalone trigger
- **Sentiment analysis of general crypto community**: This spec tracks specific known influencers, not broad social sentiment (see separate sentiment-analysis spec)
- **On-chain wallet tracking**: Tracking influencer wallets is out of scope (see whale-monitoring spec)
- **Real-time notification on individual influencer calls**: The system produces consensus scores, not per-influencer alerts
- **Influencer engagement or social features**: No following, commenting, or interacting with influencers from the platform
- **Private/paid group monitoring**: Only publicly available content
- **Automated influencer discovery**: The initial registry is manually curated; automated discovery is a future enhancement

## Acceptance Criteria

- [ ] Influencer registry holds 50-100 curated profiles across Twitter, YouTube, and Telegram
- [ ] Platform adapters poll public posts at configurable intervals per platform
- [ ] NLP classifier detects directional calls with >= 0.60 confidence threshold
- [ ] Calls are persisted with price-at-call for track record evaluation
- [ ] Track record scorer resolves calls against actual price movements after resolution window
- [ ] Reliability score per influencer calculated from hit rate, average return, lead time, and false positive rate
- [ ] Consensus engine produces `influencer_consensus_score` (0-1) per symbol
- [ ] Consensus score is published to Kafka for opportunity scorer consumption
- [ ] Opportunity scoring integrates influencer consensus with 12% weight when data is available
- [ ] TA confirmation bonus (15%) and conflict penalty (50%) applied correctly
- [ ] Anti-gaming engine detects pump-and-dump, front-running, flip-flopping, and volume spike patterns
- [ ] Flagged influencers are excluded from consensus calculation
- [ ] System functions identically when no influencer data is available (graceful degradation)
- [ ] All scraping uses official platform APIs with rate limit compliance
- [ ] Influencers can request removal from tracking (GDPR right to erasure)
- [ ] Raw posts purged after 90-day retention window
- [ ] Call detection processes posts within 60 seconds of scraping
- [ ] Consensus recalculation completes in < 5 seconds

## File Structure

```
src/main/java/com/verlumn/tradestream/influencer/
|-- BUILD
|-- InfluencerModule.kt                    # Guice module
|-- InfluencerSeed.java                    # Initial registry data
|-- SymbolAliasMap.java                    # Symbol normalization
|-- registry/
|   |-- BUILD
|   |-- InfluencerProfile.java             # Profile entity
|   |-- InfluencerRegistry.java            # Registry CRUD operations
|   |-- InfluencerRegistryDao.java         # PostgreSQL DAO
|-- scraping/
|   |-- BUILD
|   |-- PlatformAdapter.java              # Adapter interface
|   |-- TwitterAdapter.java               # Twitter/X API v2 adapter
|   |-- YouTubeAdapter.java               # YouTube Data API adapter
|   |-- TelegramAdapter.java              # Telegram Bot API adapter
|   |-- ScrapingScheduler.java            # Orchestrates polling
|-- detection/
|   |-- BUILD
|   |-- CallClassifierDoFn.java           # Beam DoFn for NLP classification
|   |-- CallDetectionPipeline.java        # Beam pipeline definition
|   |-- ClassificationResult.java         # Classification output
|-- tracking/
|   |-- BUILD
|   |-- TrackRecordScorer.java            # Call resolution and scoring
|   |-- ReliabilityScore.java             # Reliability score value object
|   |-- CallResolutionJob.java            # Scheduled resolution runner
|-- consensus/
|   |-- BUILD
|   |-- ConsensusEngine.java              # Weighted consensus calculation
|   |-- ConsensusConfig.java              # Consensus thresholds
|   |-- ConsensusResult.java              # Consensus output
|   |-- ConsensusPublisher.java           # Kafka publisher
|   |-- TaConflictDetector.java           # TA confirmation/conflict
|-- antigaming/
|   |-- BUILD
|   |-- AntiGamingEngine.java             # Gaming pattern detection
|   |-- AntiGamingConfig.java             # Detection thresholds
|   |-- GamingAnalysis.java               # Analysis result
|   |-- GamingFlag.java                   # Individual flag

src/test/java/com/verlumn/tradestream/influencer/
|-- BUILD
|-- SymbolAliasMapTest.java
|-- detection/
|   |-- BUILD
|   |-- CallClassifierDoFnTest.java
|-- tracking/
|   |-- BUILD
|   |-- TrackRecordScorerTest.java
|-- consensus/
|   |-- BUILD
|   |-- ConsensusEngineTest.java
|   |-- TaConflictDetectorTest.java
|-- antigaming/
|   |-- BUILD
|   |-- AntiGamingEngineTest.java

protos/
|-- influencer.proto                       # RawPost, DetectedCall, ConsensusSnapshot

charts/tradestream/templates/
|-- influencer-scraper.yaml
|-- influencer-call-detection.yaml
|-- influencer-track-record.yaml
|-- influencer-consensus.yaml

db/migrations/
|-- V13__influencer_profiles.sql
|-- V14__influencer_calls.sql
|-- V15__influencer_consensus_snapshots.sql
```

## Metrics

```python
# Counters
influencer_posts_scraped_total{platform}
influencer_calls_detected_total{symbol, direction}
influencer_calls_resolved_total{symbol, is_correct}
influencer_consensus_published_total{symbol}
influencer_gaming_flags_total{pattern}
influencer_api_errors_total{platform, error_type}
influencer_classification_total{result}      # call, commentary, noise

# Gauges
influencer_registry_active_count
influencer_registry_flagged_count
influencer_avg_reliability_score
influencer_consensus_score{symbol}

# Histograms
influencer_scraping_latency_ms{platform}
influencer_classification_latency_ms
influencer_consensus_calculation_ms
influencer_call_resolution_return{symbol}
influencer_call_lead_time_minutes
```

## Notes

### Cost Estimation

| Component | Cost Driver | Estimated Monthly Cost |
|-----------|------------|----------------------|
| Twitter API (Basic) | 10,000 reads/month | $100/month |
| YouTube Data API | 10,000 units/day (free) | $0 |
| Telegram Bot API | Free | $0 |
| LLM classification (Gemini Flash) | ~100K classifications/month | ~$15/month |
| Compute (4 pods) | K8s resources | Included in existing cluster |
| **Total** | | **~$115/month** |

### Migration Path

1. **Phase 1**: Registry + Twitter scraping + call detection (2 weeks)
2. **Phase 2**: Track record scoring + consensus engine (2 weeks)
3. **Phase 3**: Opportunity scoring integration + anti-gaming (1 week)
4. **Phase 4**: YouTube + Telegram adapters (1 week)
5. **Phase 5**: Monitoring, alerting, GDPR tooling (1 week)

### Dependencies

- Requires existing Kafka cluster (deployed)
- Requires existing PostgreSQL with migration framework (deployed)
- Requires existing Redis for caching (deployed)
- Requires Opportunity Scorer Agent (from `opportunity-scoring` spec)
- Requires Market Data MCP (from `signal-generator-agent` spec)

### Alternative Approaches Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Firehose social listening (all mentions) | Broader coverage | Expensive, noisy, off-spec scope | Rejected: separate sentiment spec |
| On-chain correlation (wallet tracking) | More verifiable | Complex, privacy concerns | Rejected: separate whale spec |
| Self-reported calls (influencers submit) | High accuracy | Requires influencer onboarding | Future: V2 feature |
| Community-curated registry | Scales better | Quality control issues | Future: add voting after launch |
