# News Feed Analysis

## Goal

Ingest financial news from multiple sources in real-time, extract structured events with entity resolution, and produce a `news_impact_score` (0-1) that integrates into the opportunity scoring system -- enabling TradeStream to react to market-moving news within 60 seconds of first publication.

## Target Behavior

The News Feed Analysis system operates as a streaming pipeline that:

1. Continuously ingests articles from 10+ crypto news sources via RSS, REST APIs, and WebSockets.
2. Extracts entities (coins, exchanges, people, organizations), classifies event types, and scores impact magnitude.
3. Deduplicates paraphrased coverage of the same event across sources.
4. Detects "breaking news" when 3+ sources report the same event within 5 minutes.
5. Produces a `news_impact_score` (0-1) per coin per event that feeds into opportunity scoring.
6. Triggers independent "news event" signals that can suppress or amplify TA-based signals.
7. Tracks historical accuracy of impact predictions to improve the model over time.

### End-to-End Latency Budget

```
Source publishes article            t = 0s
Feed poller / WebSocket receives    t <= 15s
NLP extraction completes            t <= 30s
Dedup + impact scoring completes    t <= 45s
Signal published to Kafka           t <= 55s
Opportunity score updated           t <= 60s   (target)
```

## Architecture

### System Overview

```
                         NEWS FEED ANALYSIS PIPELINE
  ============================================================================

  DATA SOURCES                    INGESTION                    PROCESSING
  +-----------+               +---------------+           +------------------+
  | CoinDesk  |--RSS/API----->|               |           |                  |
  | CoinTele  |--RSS/API----->|  Feed Ingest  |           |   NLP Pipeline   |
  | The Block |--RSS/API----->|   Service     |---------->|                  |
  | Decrypt   |--RSS/API----->|  (Beam/Flink) |   Kafka   |  - Entity Ext.  |
  | Reuters   |--API--------->|               |   Topic:  |  - Event Class. |
  | Bloomberg |--API--------->|               |  raw-news |  - Sentiment    |
  | Proj Blogs|--RSS--------->|               |           |  - Impact Score |
  | SEC/CFTC  |--RSS--------->|               |           |                  |
  +-----------+               +-------+-------+           +--------+---------+
                                      |                            |
                                      |                    Kafka Topic:
                                      |                   extracted-events
                                      |                            |
                              +-------v-------+           +--------v---------+
                              |               |           |                  |
                              | Feed Health   |           |  Dedup Engine    |
                              | Monitor       |           |  (MinHash LSH)  |
                              |               |           |                  |
                              +---------------+           +--------+---------+
                                                                   |
                                                           Kafka Topic:
                                                          deduped-events
                                                                   |
                                                          +--------v---------+
                                                          |                  |
                                                          | Breaking News    |
                                                          | Detector         |
                                                          | (3+ sources in   |
                                                          |  5 min window)   |
                                                          |                  |
                                                          +--------+---------+
                                                                   |
                                                           Kafka Topic:
                                                          scored-news-events
                                                                   |
                                        +-------------+------------+------------+
                                        |             |                         |
                                +-------v------+ +----v---------+  +-----------v---------+
                                |              | |              |  |                     |
                                | Opportunity  | | News Event   |  | Historical          |
                                | Score        | | Signal Gen   |  | Validator           |
                                | Integration  | | (independent |  | (price correlation) |
                                |              | |  signals)    |  |                     |
                                +--------------+ +--------------+  +-----------+---------+
                                       |               |                       |
                                Redis:          Redis:                  PostgreSQL:
                            channel:scored   channel:news          news_event_outcomes
                              -signals       -signals
```

### Kafka Topic Schema

```
Topic                    Key                  Value                Partitions  Retention
--------------------     -------------------  -------------------  ----------  ---------
news.raw-articles        source:article-id    RawArticle           6           7 days
news.extracted-events    event-hash           ExtractedNewsEvent   6           30 days
news.deduped-events      canonical-event-id   DedupedNewsEvent     6           30 days
news.scored-events       canonical-event-id   ScoredNewsEvent      6           90 days
news.breaking-alerts     coin-symbol          BreakingNewsAlert    3           7 days
```

## Data Sources

### Source Inventory and Cost Analysis

| Source | Method | Frequency | Latency | Cost | Rate Limit | Priority |
|--------|--------|-----------|---------|------|------------|----------|
| CoinDesk | RSS + REST API | 30s poll | < 5s | Free (RSS), $299/mo (API) | 100 req/min | P0 |
| CoinTelegraph | RSS | 30s poll | < 10s | Free | N/A | P0 |
| The Block | RSS + API | 30s poll | < 10s | Free (RSS), $199/mo (API) | 60 req/min | P0 |
| Decrypt | RSS | 60s poll | < 15s | Free | N/A | P1 |
| Reuters Crypto | REST API | 15s poll | < 5s | $500/mo (enterprise) | 250 req/min | P0 |
| Bloomberg Crypto | REST API | 15s poll | < 3s | $1,500/mo (terminal API) | 500 req/min | P0 |
| Project Blogs | RSS (per-project) | 60s poll | < 30s | Free | N/A | P1 |
| SEC EDGAR | RSS + REST API | 60s poll | < 60s | Free | 10 req/sec | P1 |
| CFTC | RSS | 300s poll | < 120s | Free | N/A | P2 |
| CryptoSlate | RSS | 60s poll | < 15s | Free | N/A | P2 |

**Monthly cost estimate**: $2,498/mo for full coverage ($299 + $199 + $500 + $1,500), $0/mo for free-tier-only.

### Feed Configuration

```yaml
news_feeds:
  sources:
    - name: coindesk
      type: rss
      url: "https://www.coindesk.com/arc/outboundfeeds/rss/"
      poll_interval_seconds: 30
      priority: P0
      parser: coindesk_rss
      enabled: true

    - name: coindesk_api
      type: rest_api
      base_url: "https://api.coindesk.com/v1"
      poll_interval_seconds: 15
      priority: P0
      auth:
        type: api_key
        header: "X-Api-Key"
        secret_ref: "coindesk-api-key"
      rate_limit:
        requests_per_minute: 100
      enabled: true

    - name: cointelegraph
      type: rss
      url: "https://cointelegraph.com/rss"
      poll_interval_seconds: 30
      priority: P0
      parser: generic_rss
      enabled: true

    - name: the_block
      type: rss
      url: "https://www.theblock.co/rss.xml"
      poll_interval_seconds: 30
      priority: P0
      parser: generic_rss
      enabled: true

    - name: decrypt
      type: rss
      url: "https://decrypt.co/feed"
      poll_interval_seconds: 60
      priority: P1
      parser: generic_rss
      enabled: true

    - name: reuters_crypto
      type: rest_api
      base_url: "https://api.reuters.com/v2/content"
      poll_interval_seconds: 15
      priority: P0
      auth:
        type: oauth2
        token_url: "https://auth.reuters.com/oauth/token"
        secret_ref: "reuters-credentials"
      query_filter: "topic:crypto OR topic:blockchain"
      rate_limit:
        requests_per_minute: 250
      enabled: true

    - name: bloomberg_crypto
      type: rest_api
      base_url: "https://api.bloomberg.com/news/v1"
      poll_interval_seconds: 15
      priority: P0
      auth:
        type: api_key
        header: "Authorization"
        secret_ref: "bloomberg-api-key"
      query_filter: "cryptocurrency"
      rate_limit:
        requests_per_minute: 500
      enabled: true

    - name: sec_edgar
      type: rest_api
      base_url: "https://efts.sec.gov/LATEST/search-index"
      poll_interval_seconds: 60
      priority: P1
      auth:
        type: user_agent
        value: "TradeStream/1.0 admin@tradestream.io"
      query_filter: "cryptocurrency OR bitcoin OR ethereum OR digital asset"
      rate_limit:
        requests_per_second: 10
      enabled: true

    - name: cftc
      type: rss
      url: "https://www.cftc.gov/Newsroom/PressReleases/rss"
      poll_interval_seconds: 300
      priority: P2
      parser: generic_rss
      filter_keywords: ["crypto", "digital asset", "bitcoin", "virtual currency"]
      enabled: true

    - name: project_blogs
      type: rss_multi
      feeds:
        - name: ethereum_blog
          url: "https://blog.ethereum.org/feed.xml"
          coin: ETH
        - name: solana_blog
          url: "https://solana.com/news/rss.xml"
          coin: SOL
        - name: bitcoin_dev
          url: "https://bitcoin.org/en/rss/releases.rss"
          coin: BTC
      poll_interval_seconds: 60
      priority: P1
      enabled: true
```

## Event Classification

### Taxonomy of Market-Moving Events

```
EVENT_TAXONOMY
==============

REGULATORY
  +-- BAN               Impact: 8-10   Direction: BEARISH    Example: "China bans crypto mining"
  +-- APPROVAL           Impact: 7-10   Direction: BULLISH    Example: "SEC approves spot BTC ETF"
  +-- INVESTIGATION      Impact: 5-8    Direction: BEARISH    Example: "DOJ investigates Tether"
  +-- GUIDANCE           Impact: 3-6    Direction: NEUTRAL    Example: "CFTC proposes new framework"
  +-- ENFORCEMENT        Impact: 6-9    Direction: BEARISH    Example: "SEC sues Coinbase"
  +-- LEGISLATION        Impact: 4-7    Direction: MIXED      Example: "US Senate crypto bill"

SECURITY
  +-- HACK               Impact: 7-10   Direction: BEARISH    Example: "$600M bridge exploit"
  +-- EXPLOIT            Impact: 6-9    Direction: BEARISH    Example: "Flash loan attack on DEX"
  +-- RUG_PULL           Impact: 8-10   Direction: BEARISH    Example: "Team drains liquidity"
  +-- AUDIT              Impact: 2-4    Direction: BULLISH    Example: "Trail of Bits audit passed"
  +-- VULNERABILITY      Impact: 5-8    Direction: BEARISH    Example: "Critical bug disclosed"

BUSINESS
  +-- PARTNERSHIP         Impact: 3-6    Direction: BULLISH    Example: "Visa integrates USDC"
  +-- LISTING             Impact: 4-7    Direction: BULLISH    Example: "Coinbase lists new token"
  +-- DELISTING           Impact: 5-8    Direction: BEARISH    Example: "Binance delists token"
  +-- ACQUISITION         Impact: 4-7    Direction: MIXED      Example: "Block acquires firm"
  +-- FUNDING             Impact: 3-5    Direction: BULLISH    Example: "Series B at $1B valuation"
  +-- BANKRUPTCY          Impact: 8-10   Direction: BEARISH    Example: "Exchange files Chapter 11"

TECHNICAL
  +-- UPGRADE             Impact: 3-6    Direction: BULLISH    Example: "Ethereum Dencun live"
  +-- FORK                Impact: 5-8    Direction: MIXED      Example: "Contentious hard fork"
  +-- OUTAGE              Impact: 5-8    Direction: BEARISH    Example: "Solana halted 8 hours"
  +-- MILESTONE           Impact: 2-4    Direction: BULLISH    Example: "1M validators reached"
  +-- TESTNET_LAUNCH      Impact: 2-3    Direction: BULLISH    Example: "L2 testnet goes live"

MACRO
  +-- INTEREST_RATE       Impact: 4-7    Direction: MIXED      Example: "Fed raises rates 25bps"
  +-- INFLATION           Impact: 3-6    Direction: MIXED      Example: "CPI comes in hot"
  +-- GEOPOLITICAL        Impact: 4-8    Direction: MIXED      Example: "US-China trade tensions"
  +-- MONETARY_POLICY     Impact: 5-8    Direction: MIXED      Example: "ECB starts QT"
  +-- FISCAL_POLICY       Impact: 3-6    Direction: MIXED      Example: "US debt ceiling crisis"

MARKET_STRUCTURE
  +-- ETF_APPROVAL        Impact: 8-10   Direction: BULLISH    Example: "Spot ETH ETF approved"
  +-- ETF_REJECTION       Impact: 6-8    Direction: BEARISH    Example: "ETF application denied"
  +-- INSTITUTIONAL       Impact: 4-7    Direction: BULLISH    Example: "BlackRock adds BTC"
  +-- WHALE_MOVEMENT      Impact: 3-6    Direction: MIXED      Example: "$500M BTC moved"
  +-- EXCHANGE_RESERVE    Impact: 4-7    Direction: MIXED      Example: "Exchange BTC drops 20%"
```

### Event Classification Model

```java
public enum EventCategory {
    REGULATORY, SECURITY, BUSINESS, TECHNICAL, MACRO, MARKET_STRUCTURE
}

public enum EventType {
    // Regulatory
    BAN(EventCategory.REGULATORY, 9, SentimentDirection.BEARISH),
    APPROVAL(EventCategory.REGULATORY, 8, SentimentDirection.BULLISH),
    INVESTIGATION(EventCategory.REGULATORY, 6, SentimentDirection.BEARISH),
    GUIDANCE(EventCategory.REGULATORY, 4, SentimentDirection.NEUTRAL),
    ENFORCEMENT(EventCategory.REGULATORY, 7, SentimentDirection.BEARISH),
    LEGISLATION(EventCategory.REGULATORY, 5, SentimentDirection.MIXED),

    // Security
    HACK(EventCategory.SECURITY, 9, SentimentDirection.BEARISH),
    EXPLOIT(EventCategory.SECURITY, 7, SentimentDirection.BEARISH),
    RUG_PULL(EventCategory.SECURITY, 9, SentimentDirection.BEARISH),
    AUDIT(EventCategory.SECURITY, 3, SentimentDirection.BULLISH),
    VULNERABILITY(EventCategory.SECURITY, 6, SentimentDirection.BEARISH),

    // Business
    PARTNERSHIP(EventCategory.BUSINESS, 4, SentimentDirection.BULLISH),
    LISTING(EventCategory.BUSINESS, 5, SentimentDirection.BULLISH),
    DELISTING(EventCategory.BUSINESS, 6, SentimentDirection.BEARISH),
    ACQUISITION(EventCategory.BUSINESS, 5, SentimentDirection.MIXED),
    FUNDING(EventCategory.BUSINESS, 4, SentimentDirection.BULLISH),
    BANKRUPTCY(EventCategory.BUSINESS, 9, SentimentDirection.BEARISH),

    // Technical
    UPGRADE(EventCategory.TECHNICAL, 4, SentimentDirection.BULLISH),
    FORK(EventCategory.TECHNICAL, 6, SentimentDirection.MIXED),
    OUTAGE(EventCategory.TECHNICAL, 6, SentimentDirection.BEARISH),
    MILESTONE(EventCategory.TECHNICAL, 3, SentimentDirection.BULLISH),
    TESTNET_LAUNCH(EventCategory.TECHNICAL, 2, SentimentDirection.BULLISH),

    // Macro
    INTEREST_RATE(EventCategory.MACRO, 5, SentimentDirection.MIXED),
    INFLATION(EventCategory.MACRO, 4, SentimentDirection.MIXED),
    GEOPOLITICAL(EventCategory.MACRO, 6, SentimentDirection.MIXED),
    MONETARY_POLICY(EventCategory.MACRO, 6, SentimentDirection.MIXED),
    FISCAL_POLICY(EventCategory.MACRO, 4, SentimentDirection.MIXED),

    // Market Structure
    ETF_APPROVAL(EventCategory.MARKET_STRUCTURE, 9, SentimentDirection.BULLISH),
    ETF_REJECTION(EventCategory.MARKET_STRUCTURE, 7, SentimentDirection.BEARISH),
    INSTITUTIONAL(EventCategory.MARKET_STRUCTURE, 5, SentimentDirection.BULLISH),
    WHALE_MOVEMENT(EventCategory.MARKET_STRUCTURE, 4, SentimentDirection.MIXED),
    EXCHANGE_RESERVE(EventCategory.MARKET_STRUCTURE, 5, SentimentDirection.MIXED);

    private final EventCategory category;
    private final int baseImpact;  // 1-10
    private final SentimentDirection defaultDirection;

    EventType(EventCategory category, int baseImpact, SentimentDirection direction) {
        this.category = category;
        this.baseImpact = baseImpact;
        this.defaultDirection = direction;
    }
}

public enum SentimentDirection {
    BULLISH, BEARISH, NEUTRAL, MIXED
}
```

## NLP Pipeline

### Pipeline Stages

```
  RAW ARTICLE
       |
       v
  +----+----+
  | Stage 1 |  PREPROCESSING
  | Clean   |  - Strip HTML, normalize Unicode
  | + Split |  - Split title, subtitle, body, quotes
  +---------+  - Language detection (English only for v1)
       |
       v
  +----+----+
  | Stage 2 |  ENTITY EXTRACTION
  | NER     |  - Coin mentions (BTC, Bitcoin, $BTC)
  +---------+  - People (Vitalik Buterin, Gary Gensler)
       |       - Organizations (SEC, Binance, BlackRock)
       v       - Monetary amounts ($600M, 10,000 BTC)
  +----+----+
  | Stage 3 |  EVENT CLASSIFICATION
  | Classify|  - Map to EventType taxonomy
  +---------+  - Multi-label (article may cover multiple events)
       |       - Confidence score per classification
       v
  +----+----+
  | Stage 4 |  IMPACT SCORING
  | Score   |  - Magnitude (1-10) per affected coin
  +---------+  - Directional sentiment (bullish/bearish/neutral)
       |       - Urgency (breaking/important/routine)
       v
  +----+----+
  | Stage 5 |  DEDUP / MERGE
  | Dedup   |  - MinHash LSH for near-duplicate detection
  +---------+  - Cluster articles about same event
       |       - Merge into canonical event with source count
       v
  EXTRACTED EVENT
```

### Entity Extraction

```java
/**
 * Extracts structured entities from raw article text.
 * Uses a coin symbol dictionary + NER model for people/orgs.
 */
public class NewsEntityExtractor {

    // Coin mention patterns: "$BTC", "Bitcoin", "BTC/USD", "bitcoin (BTC)"
    private static final Pattern COIN_PATTERN = Pattern.compile(
        "\\$([A-Z]{2,10})" +                      // $BTC, $ETH
        "|\\b([A-Z]{2,10})/USD\\b" +               // BTC/USD
        "|\\b(bitcoin|ethereum|solana|dogecoin|" +  // Full names
        "cardano|polkadot|avalanche|chainlink|" +
        "uniswap|aave)\\b",
        Pattern.CASE_INSENSITIVE
    );

    // Monetary amount patterns: "$600M", "1.2 billion", "10,000 BTC"
    private static final Pattern AMOUNT_PATTERN = Pattern.compile(
        "\\$([\\d,.]+)\\s*(billion|million|B|M|K|trillion|T)" +
        "|([\\d,.]+)\\s*(BTC|ETH|SOL|USDT|USDC)",
        Pattern.CASE_INSENSITIVE
    );

    private final ImmutableMap<String, String> symbolToTicker;  // "bitcoin" -> "BTC"
    private final NerModel nerModel;  // For people, organizations

    public ExtractedEntities extract(RawArticle article) {
        String fullText = article.getTitle() + " " + article.getBody();

        return ExtractedEntities.builder()
            .coins(extractCoins(fullText))
            .people(nerModel.extractPeople(fullText))
            .organizations(nerModel.extractOrganizations(fullText))
            .monetaryAmounts(extractAmounts(fullText))
            .build();
    }

    private ImmutableList<CoinMention> extractCoins(String text) {
        ImmutableList.Builder<CoinMention> coins = ImmutableList.builder();
        Matcher matcher = COIN_PATTERN.matcher(text);

        while (matcher.find()) {
            String raw = Stream.of(matcher.group(1), matcher.group(2), matcher.group(3))
                .filter(Objects::nonNull)
                .findFirst()
                .orElse("");
            String ticker = symbolToTicker.getOrDefault(
                raw.toLowerCase(), raw.toUpperCase()
            );
            int position = matcher.start();
            boolean inTitle = position < article.getTitle().length();

            coins.add(CoinMention.of(ticker, position, inTitle));
        }

        return coins.build();
    }
}
```

### Event Classification

```java
/**
 * Classifies articles into event types from the taxonomy.
 *
 * Uses a two-stage approach:
 *   1. Keyword-based fast classifier (< 1ms, catches 80% of events)
 *   2. LLM-based classifier for ambiguous cases (< 500ms, high accuracy)
 */
public class NewsEventClassifier {

    private final KeywordClassifier keywordClassifier;
    private final LlmClassifier llmClassifier;

    public ImmutableList<ClassifiedEvent> classify(
            RawArticle article,
            ExtractedEntities entities) {

        // Stage 1: Fast keyword classification
        ImmutableList<ClassifiedEvent> keywordResults =
            keywordClassifier.classify(article);

        // If high confidence (> 0.85), use keyword result directly
        if (keywordResults.stream().anyMatch(e -> e.confidence() > 0.85)) {
            return keywordResults;
        }

        // Stage 2: LLM classification for ambiguous cases
        return llmClassifier.classify(article, entities, keywordResults);
    }
}

/**
 * Keyword-based classifier using weighted term matching.
 */
public class KeywordClassifier {

    private static final ImmutableMap<EventType, ImmutableList<WeightedKeyword>> RULES =
        ImmutableMap.<EventType, ImmutableList<WeightedKeyword>>builder()
            .put(EventType.HACK, ImmutableList.of(
                WeightedKeyword.of("hack", 0.8),
                WeightedKeyword.of("exploit", 0.7),
                WeightedKeyword.of("drained", 0.8),
                WeightedKeyword.of("stolen", 0.7),
                WeightedKeyword.of("breach", 0.6),
                WeightedKeyword.of("compromised", 0.6)
            ))
            .put(EventType.ETF_APPROVAL, ImmutableList.of(
                WeightedKeyword.of("etf approved", 0.95),
                WeightedKeyword.of("etf approval", 0.90),
                WeightedKeyword.of("spot etf", 0.7),
                WeightedKeyword.of("sec approves", 0.85)
            ))
            .put(EventType.BAN, ImmutableList.of(
                WeightedKeyword.of("ban", 0.6),
                WeightedKeyword.of("prohibit", 0.7),
                WeightedKeyword.of("illegal", 0.5),
                WeightedKeyword.of("crackdown", 0.6)
            ))
            // ... additional event types
            .build();
}

/**
 * LLM-based classifier for nuanced event classification.
 */
public class LlmClassifier {

    private static final String CLASSIFICATION_PROMPT = """
        Classify the following crypto news article into event types.

        ARTICLE:
        Title: %s
        Body (first 500 chars): %s

        ENTITIES FOUND:
        Coins: %s
        Organizations: %s

        EVENT TYPES (choose 1-3):
        REGULATORY: BAN, APPROVAL, INVESTIGATION, GUIDANCE, ENFORCEMENT, LEGISLATION
        SECURITY: HACK, EXPLOIT, RUG_PULL, AUDIT, VULNERABILITY
        BUSINESS: PARTNERSHIP, LISTING, DELISTING, ACQUISITION, FUNDING, BANKRUPTCY
        TECHNICAL: UPGRADE, FORK, OUTAGE, MILESTONE, TESTNET_LAUNCH
        MACRO: INTEREST_RATE, INFLATION, GEOPOLITICAL, MONETARY_POLICY, FISCAL_POLICY
        MARKET_STRUCTURE: ETF_APPROVAL, ETF_REJECTION, INSTITUTIONAL, WHALE_MOVEMENT

        Respond as JSON:
        {
          "events": [
            {"type": "EVENT_TYPE", "confidence": 0.0-1.0, "reasoning": "..."}
          ],
          "primary_event": "EVENT_TYPE"
        }
        """;
}
```

### Impact Magnitude Scoring

```java
/**
 * Scores the market impact of a classified news event on a scale of 1-10.
 *
 * Factors considered:
 *   - Base impact from event type taxonomy (e.g., HACK = 9)
 *   - Source credibility weight (Reuters > CryptoSlate)
 *   - Monetary magnitude (if applicable)
 *   - Entity prominence (BTC/ETH vs micro-cap)
 *   - Recency of similar events (fatigue dampening)
 */
public class ImpactScorer {

    private static final ImmutableMap<String, Double> SOURCE_CREDIBILITY =
        ImmutableMap.<String, Double>builder()
            .put("reuters", 1.0)
            .put("bloomberg", 1.0)
            .put("coindesk", 0.9)
            .put("the_block", 0.85)
            .put("cointelegraph", 0.8)
            .put("decrypt", 0.75)
            .put("sec_edgar", 1.0)
            .put("cftc", 1.0)
            .put("project_blogs", 0.7)
            .put("cryptoslate", 0.6)
            .buildOrThrow();

    private static final ImmutableMap<String, Double> COIN_PROMINENCE =
        ImmutableMap.<String, Double>builder()
            .put("BTC", 1.0)
            .put("ETH", 0.95)
            .put("SOL", 0.7)
            .put("BNB", 0.65)
            .put("XRP", 0.6)
            .put("DOGE", 0.5)
            .buildOrThrow();

    /**
     * Calculate impact score (1-10) for an event affecting a specific coin.
     *
     * @param event       The classified event
     * @param coin        The affected coin ticker
     * @param sourceCount Number of sources reporting (for breaking detection)
     * @return Impact score 1-10
     */
    public double scoreImpact(
            ClassifiedEvent event,
            String coin,
            int sourceCount,
            List<MonetaryAmount> amounts) {

        double baseImpact = event.getType().getBaseImpact();

        // Source credibility adjustment (-20% to +0%)
        double credibility = SOURCE_CREDIBILITY.getOrDefault(
            event.getSource(), 0.5
        );
        double credibilityFactor = 0.8 + (0.2 * credibility);

        // Monetary magnitude adjustment (+0% to +30%)
        double magnitudeFactor = 1.0;
        if (!amounts.isEmpty()) {
            double maxUsd = amounts.stream()
                .mapToDouble(MonetaryAmount::toUsd)
                .max().orElse(0);
            // Log scale: $1M = +5%, $100M = +15%, $1B+ = +30%
            if (maxUsd > 0) {
                magnitudeFactor = 1.0 + Math.min(0.3,
                    0.05 * Math.log10(maxUsd / 1_000_000));
            }
        }

        // Coin prominence adjustment (-30% to +0%)
        double prominence = COIN_PROMINENCE.getOrDefault(coin, 0.3);
        double prominenceFactor = 0.7 + (0.3 * prominence);

        // Multi-source amplification (+0% to +20%)
        double sourceFactor = 1.0 + Math.min(0.2,
            0.05 * (sourceCount - 1));

        // Fatigue dampening: reduce impact if similar events occurred recently
        double fatigueFactor = calculateFatigueFactor(event.getType(), coin);

        double rawScore = baseImpact
            * credibilityFactor
            * magnitudeFactor
            * prominenceFactor
            * sourceFactor
            * fatigueFactor;

        // Clamp to 1-10
        return Math.max(1.0, Math.min(10.0, rawScore));
    }

    /**
     * Reduce impact for repeated event types (e.g., 3rd hack this week).
     * First event = 100%, second within 24h = 80%, third = 60%.
     */
    private double calculateFatigueFactor(EventType type, String coin) {
        int recentCount = eventStore.countRecent(type, coin, Duration.ofHours(24));
        return Math.max(0.4, 1.0 - (0.2 * recentCount));
    }
}
```

### Sentiment Analysis

```java
/**
 * Determines sentiment polarity for an article relative to each mentioned coin.
 *
 * Returns a SentimentResult per coin with:
 *   - polarity: -1.0 (very bearish) to +1.0 (very bullish)
 *   - confidence: 0.0 to 1.0
 */
public class NewsSentimentAnalyzer {

    /**
     * Combines event-type default sentiment with article-specific language cues.
     */
    public SentimentResult analyzeSentiment(
            ClassifiedEvent event,
            RawArticle article,
            String targetCoin) {

        // Start with event-type default direction
        double basePolarity = switch (event.getType().getDefaultDirection()) {
            case BULLISH -> 0.5;
            case BEARISH -> -0.5;
            case NEUTRAL -> 0.0;
            case MIXED -> 0.0;
        };

        // Adjust with keyword sentiment from article body
        double keywordPolarity = keywordSentiment.score(article.getBody());

        // Weighted combination
        double polarity = (0.6 * basePolarity) + (0.4 * keywordPolarity);

        // Context-specific adjustments
        polarity = applyContextAdjustments(polarity, event, targetCoin);

        return SentimentResult.of(
            Math.max(-1.0, Math.min(1.0, polarity)),
            event.getConfidence()
        );
    }

    /**
     * Adjust sentiment based on event context.
     * Example: A "hack" on a competing exchange may be slightly bullish
     * for other exchanges.
     */
    private double applyContextAdjustments(
            double polarity,
            ClassifiedEvent event,
            String targetCoin) {

        // If event mentions a specific coin and target is different,
        // invert or dampen sentiment for indirect effects
        if (!event.getPrimaryCoin().equals(targetCoin)) {
            // Competitor effect: hack on exchange X may benefit exchange Y
            if (event.getType().getCategory() == EventCategory.SECURITY) {
                polarity *= -0.2;  // Slight inverse effect
            } else {
                polarity *= 0.3;   // Dampened spillover
            }
        }

        return polarity;
    }
}
```

### Duplicate / Paraphrase Detection

```java
/**
 * Detects duplicate and paraphrased articles about the same event.
 *
 * Uses MinHash + Locality-Sensitive Hashing (LSH) for near-duplicate detection.
 * Two articles are considered duplicates if:
 *   1. Jaccard similarity of 3-gram shingles > 0.6, OR
 *   2. They share the same (EventType, PrimaryCoin) and publish within 30 min
 *      of each other with title cosine similarity > 0.7
 */
public class ArticleDeduplicator {

    private static final int NUM_HASHES = 128;
    private static final double SIMILARITY_THRESHOLD = 0.6;
    private static final Duration TIME_WINDOW = Duration.ofMinutes(30);

    private final MinHashIndex minHashIndex;
    private final EventClusterStore clusterStore;

    /**
     * Check if article is a duplicate and return the canonical event ID.
     *
     * @return Optional canonical event ID if this is a duplicate
     */
    public Optional<String> findDuplicate(ExtractedNewsEvent event) {
        // Step 1: MinHash similarity check
        int[] signature = minHash(event.getNormalizedText(), NUM_HASHES);
        List<String> candidates = minHashIndex.query(signature, SIMILARITY_THRESHOLD);

        for (String candidateId : candidates) {
            ExtractedNewsEvent candidate = clusterStore.get(candidateId);
            if (candidate != null && isSameEvent(event, candidate)) {
                return Optional.of(candidate.getCanonicalEventId());
            }
        }

        // Step 2: Semantic cluster check (same event type + coin + time window)
        Optional<String> semanticMatch = clusterStore.findCluster(
            event.getPrimaryEventType(),
            event.getPrimaryCoin(),
            event.getPublishedAt(),
            TIME_WINDOW
        );

        if (semanticMatch.isPresent()) {
            // Verify with title similarity
            ExtractedNewsEvent clusterHead = clusterStore.get(semanticMatch.get());
            if (titleSimilarity(event, clusterHead) > 0.7) {
                return semanticMatch;
            }
        }

        return Optional.empty();
    }

    /**
     * Register a new event (either as new canonical event or merged into existing).
     */
    public DedupedNewsEvent registerEvent(ExtractedNewsEvent event) {
        Optional<String> existingId = findDuplicate(event);

        if (existingId.isPresent()) {
            // Merge into existing canonical event
            return clusterStore.mergeSource(existingId.get(), event);
        } else {
            // Create new canonical event
            String canonicalId = generateCanonicalId(event);
            int[] signature = minHash(event.getNormalizedText(), NUM_HASHES);
            minHashIndex.insert(canonicalId, signature);

            return clusterStore.createCanonical(canonicalId, event);
        }
    }
}
```

## Breaking News Detection

```java
/**
 * Detects breaking news: an event reported by 3+ independent sources
 * within a 5-minute sliding window.
 *
 * Uses a Flink CEP (Complex Event Processing) pattern on the
 * news.deduped-events Kafka topic.
 */
public class BreakingNewsDetector extends KeyedProcessFunction<
        String,           // key: canonical-event-id
        DedupedNewsEvent, // input: deduped events
        BreakingNewsAlert // output: breaking alerts
    > {

    private static final int BREAKING_SOURCE_THRESHOLD = 3;
    private static final Duration BREAKING_WINDOW = Duration.ofMinutes(5);

    // State: set of unique source names for each canonical event
    private MapState<String, Set<String>> eventSourcesState;
    // State: first-seen timestamp per canonical event
    private ValueState<Long> firstSeenState;
    // State: whether we already emitted a breaking alert
    private ValueState<Boolean> alertEmittedState;

    @Override
    public void open(Configuration config) {
        eventSourcesState = getRuntimeContext().getMapState(
            new MapStateDescriptor<>("event-sources",
                String.class, TypeInformation.of(new TypeHint<Set<String>>() {}))
        );
        firstSeenState = getRuntimeContext().getState(
            new ValueStateDescriptor<>("first-seen", Long.class)
        );
        alertEmittedState = getRuntimeContext().getState(
            new ValueStateDescriptor<>("alert-emitted", Boolean.class)
        );
    }

    @Override
    public void processElement(
            DedupedNewsEvent event,
            Context ctx,
            Collector<BreakingNewsAlert> out) throws Exception {

        String canonicalId = event.getCanonicalEventId();

        // Initialize first-seen timestamp
        if (firstSeenState.value() == null) {
            firstSeenState.update(ctx.timerService().currentProcessingTime());
            // Register timer for window expiration
            ctx.timerService().registerProcessingTimeTimer(
                ctx.timerService().currentProcessingTime()
                    + BREAKING_WINDOW.toMillis()
            );
        }

        // Track unique sources
        Set<String> sources = eventSourcesState.get(canonicalId);
        if (sources == null) {
            sources = new HashSet<>();
        }
        sources.add(event.getSourceName());
        eventSourcesState.put(canonicalId, sources);

        // Check if breaking threshold reached
        if (sources.size() >= BREAKING_SOURCE_THRESHOLD
                && !Boolean.TRUE.equals(alertEmittedState.value())) {

            long latencyMs = ctx.timerService().currentProcessingTime()
                - firstSeenState.value();

            BreakingNewsAlert alert = BreakingNewsAlert.newBuilder()
                .setCanonicalEventId(canonicalId)
                .setEventType(event.getPrimaryEventType())
                .setPrimaryCoin(event.getPrimaryCoin())
                .setSourceCount(sources.size())
                .setSources(ImmutableList.copyOf(sources))
                .setImpactScore(event.getImpactScore())
                .setSentiment(event.getSentiment())
                .setDetectionLatencyMs(latencyMs)
                .setTimestamp(Instant.now())
                .setHeadline(event.getHeadline())
                .build();

            out.collect(alert);
            alertEmittedState.update(true);

            // Metric: breaking news detection latency
            metrics.histogram("breaking_news_latency_ms", latencyMs);
            metrics.increment("breaking_news_detected",
                ImmutableMap.of(
                    "event_type", event.getPrimaryEventType().name(),
                    "coin", event.getPrimaryCoin()
                ));
        }
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx,
            Collector<BreakingNewsAlert> out) throws Exception {
        // Window expired -- clean up state
        eventSourcesState.clear();
        firstSeenState.clear();
        alertEmittedState.clear();
    }
}
```

## Integration with Opportunity Scoring

### News Impact Score (0-1)

The `news_impact_score` translates raw impact (1-10) and sentiment into a [0, 1] modifier for opportunity scoring.

```python
def calculate_news_impact_score(
    impact_magnitude: float,      # 1-10 from ImpactScorer
    sentiment_polarity: float,    # -1.0 to +1.0
    sentiment_confidence: float,  # 0.0 to 1.0
    source_count: int,            # number of sources reporting
    is_breaking: bool,            # 3+ sources in 5 min
    minutes_since_event: float,   # how old the news is
    signal_action: str            # BUY or SELL -- the TA signal action
) -> float:
    """
    Calculate news_impact_score (0-1) that integrates into opportunity scoring.

    Interpretation:
      0.0 = strong headwind (news contradicts TA signal direction)
      0.5 = neutral (no relevant news, or news is ambiguous)
      1.0 = strong tailwind (news confirms TA signal direction)

    Returns:
        Float between 0.0 and 1.0
    """
    # Determine if news aligns with signal direction
    # BUY signal + bullish news = aligned; BUY signal + bearish news = opposed
    if signal_action == "BUY":
        alignment = sentiment_polarity  # +1 = aligned, -1 = opposed
    else:  # SELL
        alignment = -sentiment_polarity  # -1 sentiment = aligned with SELL

    # Scale alignment by impact magnitude (higher impact = stronger effect)
    magnitude_weight = impact_magnitude / 10.0

    # Confidence-weighted alignment
    weighted_alignment = alignment * magnitude_weight * sentiment_confidence

    # Breaking news amplification (+30%)
    if is_breaking:
        weighted_alignment *= 1.3

    # Multi-source amplification (+5% per additional source, max +20%)
    source_bonus = min(0.2, 0.05 * max(0, source_count - 1))
    weighted_alignment *= (1.0 + source_bonus)

    # Time decay: news impact halves every 2 hours
    decay_factor = 0.5 ** (minutes_since_event / 120.0)
    weighted_alignment *= decay_factor

    # Map from [-1, 1] to [0, 1]
    news_impact_score = 0.5 + (0.5 * weighted_alignment)

    return max(0.0, min(1.0, news_impact_score))
```

### Updated Opportunity Score Formula

With news integration, the opportunity scoring formula gains a new `news_impact` factor. The existing weights are rebalanced to incorporate the new signal:

```python
# BEFORE (original weights):
#   confidence:      25%
#   expected_return: 30%
#   consensus:       20%
#   volatility:      15%
#   freshness:       10%

# AFTER (with news integration):
#   confidence:      22%
#   expected_return: 27%
#   consensus:       18%
#   volatility:      13%
#   freshness:        8%
#   news_impact:     12%   <-- NEW

def calculate_opportunity_score_with_news(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    market_regime: str,
    news_impact_score: float = 0.5   # Default: neutral (no news)
) -> float:
    """
    Extended opportunity score incorporating news impact.
    """
    caps = get_regime_adjusted_caps(market_regime)

    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)
    volatility_score = min(volatility / caps.max_volatility, 1.0)
    freshness_score = max(0, 1 - (minutes_ago / 60))

    opportunity_score = (
        0.22 * confidence +
        0.27 * return_score +
        0.18 * consensus_pct +
        0.13 * volatility_score +
        0.08 * freshness_score +
        0.12 * news_impact_score      # NEW: news factor
    ) * 100

    return round(opportunity_score, 1)
```

### News-Based Signal Suppression

Major negative events should suppress BUY signals even when TA indicators are bullish. This is handled by a signal gate that sits between the signal generator and the scorer.

```java
/**
 * Gates TA signals based on active news events.
 *
 * A SUPPRESS decision blocks BUY signals when major negative news is
 * active for the coin. A BOOST decision adds weight to signals that
 * align with breaking news.
 */
public class NewsSignalGate {

    private static final double SUPPRESS_THRESHOLD = 7.0;  // impact >= 7 suppresses
    private static final Duration SUPPRESS_WINDOW = Duration.ofMinutes(30);

    public enum GateDecision {
        PASS,       // No relevant news, let signal through
        SUPPRESS,   // Major negative news, block BUY signals
        BOOST       // Positive breaking news, amplify signal
    }

    /**
     * Evaluate whether a TA signal should be passed, suppressed, or boosted.
     */
    public GateResult evaluate(TradeSignal taSignal, String coin) {
        List<ScoredNewsEvent> activeEvents = newsEventStore.getActiveEvents(
            coin, SUPPRESS_WINDOW
        );

        if (activeEvents.isEmpty()) {
            return GateResult.of(GateDecision.PASS, 1.0, "No active news events");
        }

        // Find highest-impact negative event
        Optional<ScoredNewsEvent> worstEvent = activeEvents.stream()
            .filter(e -> e.getSentiment().getPolarity() < -0.3)
            .max(Comparator.comparingDouble(ScoredNewsEvent::getImpactScore));

        // Suppress BUY signals during major negative events
        if (worstEvent.isPresent()
                && worstEvent.get().getImpactScore() >= SUPPRESS_THRESHOLD
                && taSignal.getType() == TradeSignalType.BUY) {

            return GateResult.of(
                GateDecision.SUPPRESS,
                0.0,
                String.format(
                    "BUY suppressed: %s (impact=%.1f, source_count=%d)",
                    worstEvent.get().getHeadline(),
                    worstEvent.get().getImpactScore(),
                    worstEvent.get().getSourceCount()
                )
            );
        }

        // Boost signals aligned with breaking positive news
        Optional<ScoredNewsEvent> bestEvent = activeEvents.stream()
            .filter(ScoredNewsEvent::isBreaking)
            .filter(e -> e.getSentiment().getPolarity() > 0.3)
            .max(Comparator.comparingDouble(ScoredNewsEvent::getImpactScore));

        if (bestEvent.isPresent()
                && taSignal.getType() == TradeSignalType.BUY) {
            double boostFactor = 1.0 + (bestEvent.get().getImpactScore() / 20.0);
            return GateResult.of(
                GateDecision.BOOST,
                boostFactor,
                String.format(
                    "BUY boosted by breaking news: %s",
                    bestEvent.get().getHeadline()
                )
            );
        }

        return GateResult.of(GateDecision.PASS, 1.0, "News present but not actionable");
    }
}
```

### Independent News Event Signals

News events with impact >= 7 generate standalone signals separate from TA. These appear in the signal stream with a `NEWS_EVENT` source type.

```java
/**
 * Generates independent trading signals from high-impact news events.
 *
 * Unlike TA signals which require strategy consensus, news signals are
 * generated directly from a single high-impact event.
 */
public class NewsSignalGenerator {

    private static final double MIN_IMPACT_FOR_SIGNAL = 7.0;
    private static final double MIN_CONFIDENCE = 0.6;

    public Optional<TradeSignal> generateSignal(ScoredNewsEvent event) {
        if (event.getImpactScore() < MIN_IMPACT_FOR_SIGNAL) {
            return Optional.empty();
        }

        if (event.getSentiment().getConfidence() < MIN_CONFIDENCE) {
            return Optional.empty();
        }

        TradeSignalType signalType;
        if (event.getSentiment().getPolarity() > 0.3) {
            signalType = TradeSignalType.BUY;
        } else if (event.getSentiment().getPolarity() < -0.3) {
            signalType = TradeSignalType.SELL;
        } else {
            return Optional.empty();  // Ambiguous sentiment, no signal
        }

        String reason = String.format(
            "[NEWS] %s | Impact: %.1f/10 | Sources: %d | %s",
            event.getHeadline(),
            event.getImpactScore(),
            event.getSourceCount(),
            event.isBreaking() ? "BREAKING" : "Standard"
        );

        TradeSignal signal = TradeSignal.newBuilder()
            .setType(signalType)
            .setTimestamp(Instant.now().toEpochMilli())
            .setReason(reason)
            .build();

        return Optional.of(signal);
    }
}
```

### Suppression Example: Exchange Hack

```
SCENARIO: Major exchange hack reported ($400M stolen)
=========================================================

t=0s   CoinDesk publishes: "Major Exchange Hacked for $400M"
t=12s  Feed poller picks up article
t=25s  NLP pipeline extracts:
         - EventType: HACK
         - Coin: BTC (general market), exchange token
         - Impact magnitude: 9.2/10
         - Sentiment: -0.85 (very bearish)
         - Monetary amount: $400M

t=35s  Dedup engine: new canonical event (no duplicates yet)

t=60s  The Block publishes same story
t=90s  CoinTelegraph publishes same story

t=95s  Breaking news detected: 3 sources in < 5 min
         - Impact boosted to 9.5/10 (multi-source amplification)
         - BreakingNewsAlert emitted to news.breaking-alerts

t=100s TA signal arrives: BUY ETH/USD (RSI oversold bounce)
         - NewsSignalGate evaluates:
           Active event: HACK, impact=9.5, sentiment=-0.85
           Decision: SUPPRESS
           Reason: "BUY suppressed: Major Exchange Hack (impact=9.5, sources=3)"
         - BUY signal is BLOCKED from reaching opportunity scorer

t=100s Independent news signal generated:
         - Type: SELL
         - Reason: "[NEWS] Major Exchange Hacked for $400M | Impact: 9.5/10 |
                     Sources: 3 | BREAKING"
         - Published to channel:news-signals

t=30min Suppression window expires
         - New TA signals flow normally
         - news_impact_score gradually returns toward 0.5 (neutral)
```

## Historical Validation

### Price Correlation Tracking

```java
/**
 * Tracks news events and correlates with subsequent price movements to
 * validate and calibrate the impact model.
 *
 * For each scored news event:
 *   1. Record the predicted impact (magnitude + direction)
 *   2. Snapshot the price at event detection time
 *   3. Measure actual price change at t+5m, t+15m, t+1h, t+4h, t+24h
 *   4. Compare predicted vs actual to compute model accuracy
 */
public class NewsImpactValidator {

    private static final List<Duration> MEASUREMENT_WINDOWS = List.of(
        Duration.ofMinutes(5),
        Duration.ofMinutes(15),
        Duration.ofHours(1),
        Duration.ofHours(4),
        Duration.ofHours(24)
    );

    /**
     * Record an event for future validation.
     */
    public void recordEvent(ScoredNewsEvent event) {
        double priceAtDetection = marketData.getPrice(event.getPrimaryCoin());

        NewsEventOutcome outcome = NewsEventOutcome.builder()
            .canonicalEventId(event.getCanonicalEventId())
            .eventType(event.getPrimaryEventType())
            .coin(event.getPrimaryCoin())
            .predictedImpact(event.getImpactScore())
            .predictedDirection(event.getSentiment().getPolarity())
            .sourceCount(event.getSourceCount())
            .isBreaking(event.isBreaking())
            .priceAtDetection(priceAtDetection)
            .detectedAt(Instant.now())
            .build();

        outcomeStore.save(outcome);

        // Schedule price checks at each measurement window
        for (Duration window : MEASUREMENT_WINDOWS) {
            scheduler.schedule(
                () -> measureOutcome(outcome.getCanonicalEventId(), window),
                window
            );
        }
    }

    /**
     * Measure actual price change at a measurement window.
     */
    private void measureOutcome(String eventId, Duration window) {
        NewsEventOutcome outcome = outcomeStore.get(eventId);
        if (outcome == null) return;

        double currentPrice = marketData.getPrice(outcome.getCoin());
        double priceChange = (currentPrice - outcome.getPriceAtDetection())
            / outcome.getPriceAtDetection();

        String windowLabel = formatWindow(window);
        outcomeStore.recordMeasurement(eventId, windowLabel, priceChange);

        // Update running accuracy metrics
        updateAccuracyMetrics(outcome, priceChange, windowLabel);
    }

    /**
     * Compare predicted direction with actual price movement.
     */
    private void updateAccuracyMetrics(
            NewsEventOutcome outcome,
            double actualPriceChange,
            String window) {

        boolean predictedBullish = outcome.getPredictedDirection() > 0.1;
        boolean predictedBearish = outcome.getPredictedDirection() < -0.1;
        boolean actuallyRose = actualPriceChange > 0.005;   // > 0.5%
        boolean actuallyFell = actualPriceChange < -0.005;

        boolean directionCorrect =
            (predictedBullish && actuallyRose) ||
            (predictedBearish && actuallyFell);

        metrics.increment("news_prediction_total", ImmutableMap.of(
            "event_type", outcome.getEventType().name(),
            "window", window,
            "correct", String.valueOf(directionCorrect)
        ));

        // Magnitude accuracy: predicted impact vs actual magnitude
        double predictedMagnitude = outcome.getPredictedImpact() / 10.0;
        double actualMagnitude = Math.abs(actualPriceChange) * 100; // Rough scale
        double magnitudeError = Math.abs(predictedMagnitude - actualMagnitude);

        metrics.histogram("news_magnitude_error", magnitudeError, ImmutableMap.of(
            "event_type", outcome.getEventType().name(),
            "window", window
        ));
    }
}
```

### PostgreSQL Schema for Historical Tracking

```sql
CREATE TABLE news_events (
    canonical_event_id  VARCHAR(64) PRIMARY KEY,
    event_type          VARCHAR(32) NOT NULL,
    category            VARCHAR(32) NOT NULL,
    primary_coin        VARCHAR(10) NOT NULL,
    headline            TEXT NOT NULL,
    impact_score        DECIMAL(4,2) NOT NULL,
    sentiment_polarity  DECIMAL(4,3) NOT NULL,
    sentiment_confidence DECIMAL(4,3) NOT NULL,
    source_count        INTEGER NOT NULL,
    is_breaking         BOOLEAN NOT NULL DEFAULT FALSE,
    sources             TEXT[] NOT NULL,       -- Array of source names
    detected_at         TIMESTAMP WITH TIME ZONE NOT NULL,
    first_published_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    detection_latency_ms INTEGER,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE news_event_outcomes (
    id                  SERIAL PRIMARY KEY,
    canonical_event_id  VARCHAR(64) NOT NULL REFERENCES news_events(canonical_event_id),
    coin                VARCHAR(10) NOT NULL,
    price_at_detection  DECIMAL(18,8) NOT NULL,
    price_at_5m         DECIMAL(18,8),
    price_at_15m        DECIMAL(18,8),
    price_at_1h         DECIMAL(18,8),
    price_at_4h         DECIMAL(18,8),
    price_at_24h        DECIMAL(18,8),
    change_5m           DECIMAL(10,6),
    change_15m          DECIMAL(10,6),
    change_1h           DECIMAL(10,6),
    change_4h           DECIMAL(10,6),
    change_24h          DECIMAL(10,6),
    direction_correct_5m  BOOLEAN,
    direction_correct_15m BOOLEAN,
    direction_correct_1h  BOOLEAN,
    direction_correct_4h  BOOLEAN,
    direction_correct_24h BOOLEAN,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_news_events_coin ON news_events(primary_coin, detected_at);
CREATE INDEX idx_news_events_type ON news_events(event_type, detected_at);
CREATE INDEX idx_news_outcomes_event ON news_event_outcomes(canonical_event_id);

-- View for model accuracy dashboard
CREATE VIEW news_model_accuracy AS
SELECT
    event_type,
    COUNT(*) as total_events,
    AVG(CASE WHEN direction_correct_1h THEN 1.0 ELSE 0.0 END) as accuracy_1h,
    AVG(CASE WHEN direction_correct_4h THEN 1.0 ELSE 0.0 END) as accuracy_4h,
    AVG(CASE WHEN direction_correct_24h THEN 1.0 ELSE 0.0 END) as accuracy_24h,
    AVG(ABS(change_1h)) as avg_actual_magnitude_1h,
    AVG(impact_score) as avg_predicted_impact
FROM news_event_outcomes o
JOIN news_events e ON e.canonical_event_id = o.canonical_event_id
GROUP BY event_type;
```

## Implementation

### Beam Pipeline (Feed Ingestion)

```java
/**
 * Apache Beam pipeline for news feed ingestion.
 * Runs on Flink, reads from configured feed sources,
 * and writes raw articles to Kafka.
 */
public class NewsFeedIngestionPipeline {

    public static Pipeline create(PipelineOptions options, NewsConfig config) {
        Pipeline pipeline = Pipeline.create(options);

        // Create a PCollection per source, then flatten
        PCollectionList<RawArticle> allFeeds = PCollectionList.empty(pipeline);

        for (FeedSourceConfig source : config.getSources()) {
            if (!source.isEnabled()) continue;

            PCollection<RawArticle> feed;
            switch (source.getType()) {
                case RSS:
                    feed = pipeline
                        .apply("ReadRSS-" + source.getName(),
                            GenerateSequence.from(0)
                                .withRate(1,
                                    org.joda.time.Duration.standardSeconds(
                                        source.getPollIntervalSeconds())))
                        .apply("FetchRSS-" + source.getName(),
                            ParDo.of(new RssFetcherFn(source)));
                    break;
                case REST_API:
                    feed = pipeline
                        .apply("ReadAPI-" + source.getName(),
                            GenerateSequence.from(0)
                                .withRate(1,
                                    org.joda.time.Duration.standardSeconds(
                                        source.getPollIntervalSeconds())))
                        .apply("FetchAPI-" + source.getName(),
                            ParDo.of(new RestApiFetcherFn(source)));
                    break;
                default:
                    continue;
            }

            allFeeds = allFeeds.and(
                feed.apply("Tag-" + source.getName(),
                    WithKeys.of(source.getName()))
            );
        }

        // Flatten all feeds and write to Kafka
        allFeeds.apply("Flatten", Flatten.pCollections())
            .apply("ToKafka", KafkaIO.<String, RawArticle>write()
                .withBootstrapServers(config.getKafkaBootstrap())
                .withTopic("news.raw-articles")
                .withKeySerializer(StringSerializer.class)
                .withValueSerializer(RawArticleSerializer.class));

        return pipeline;
    }
}
```

### Feed Health Monitor

```java
/**
 * Monitors health of each news feed source.
 * Alerts when a feed stops producing articles (may indicate outage or config error).
 */
public class FeedHealthMonitor {

    private final Map<String, Instant> lastArticleTime = new ConcurrentHashMap<>();
    private final Duration staleThreshold = Duration.ofMinutes(15);

    /**
     * Record article arrival from a source.
     */
    public void recordArticle(String sourceName) {
        lastArticleTime.put(sourceName, Instant.now());
        metrics.increment("feed_articles_ingested", ImmutableMap.of("source", sourceName));
    }

    /**
     * Check all feeds for staleness. Called every 60 seconds.
     */
    @Scheduled(fixedRate = 60_000)
    public void checkFeedHealth() {
        for (Map.Entry<String, Instant> entry : lastArticleTime.entrySet()) {
            Duration sinceLastArticle = Duration.between(entry.getValue(), Instant.now());
            if (sinceLastArticle.compareTo(staleThreshold) > 0) {
                metrics.gauge("feed_stale", 1, ImmutableMap.of(
                    "source", entry.getKey(),
                    "minutes_stale", String.valueOf(sinceLastArticle.toMinutes())
                ));
                log.atWarning().log(
                    "Feed %s has been stale for %d minutes",
                    entry.getKey(), sinceLastArticle.toMinutes()
                );
            } else {
                metrics.gauge("feed_stale", 0, ImmutableMap.of(
                    "source", entry.getKey()
                ));
            }
        }
    }
}
```

### Data Models (Protocol Buffers)

```protobuf
// protos/news_events.proto

edition = "2023";

package news;

option java_multiple_files = true;
option java_package = "com.verlumen.tradestream.news";

import "google/protobuf/timestamp.proto";

message RawArticle {
  string article_id = 1;
  string source_name = 2;
  string url = 3;
  string title = 4;
  string subtitle = 5;
  string body = 6;
  string author = 7;
  google.protobuf.Timestamp published_at = 8;
  google.protobuf.Timestamp ingested_at = 9;
  repeated string tags = 10;
}

message ExtractedNewsEvent {
  string event_id = 1;
  string article_id = 2;
  string source_name = 3;
  string headline = 4;

  // Extracted entities
  repeated CoinMention coins = 5;
  repeated string organizations = 6;
  repeated string people = 7;
  repeated MonetaryAmount amounts = 8;

  // Classification
  EventType primary_event_type = 9;
  repeated EventClassification classifications = 10;

  // Scoring
  double impact_magnitude = 11;    // 1-10
  double sentiment_polarity = 12;  // -1.0 to +1.0
  double sentiment_confidence = 13; // 0.0 to 1.0

  google.protobuf.Timestamp published_at = 14;
  google.protobuf.Timestamp extracted_at = 15;
}

message CoinMention {
  string ticker = 1;          // e.g., "BTC"
  int32 position = 2;         // character position in text
  bool in_title = 3;          // whether mention is in title
}

message MonetaryAmount {
  double value = 1;
  string currency = 2;        // "USD", "BTC", "ETH"
  double usd_equivalent = 3;
}

message EventClassification {
  EventType event_type = 1;
  double confidence = 2;
}

enum EventType {
  EVENT_TYPE_UNKNOWN = 0;

  // Regulatory
  BAN = 1;
  APPROVAL = 2;
  INVESTIGATION = 3;
  GUIDANCE = 4;
  ENFORCEMENT = 5;
  LEGISLATION = 6;

  // Security
  HACK = 10;
  EXPLOIT = 11;
  RUG_PULL = 12;
  AUDIT = 13;
  VULNERABILITY = 14;

  // Business
  PARTNERSHIP = 20;
  LISTING = 21;
  DELISTING = 22;
  ACQUISITION = 23;
  FUNDING = 24;
  BANKRUPTCY = 25;

  // Technical
  UPGRADE = 30;
  FORK = 31;
  OUTAGE = 32;
  MILESTONE = 33;
  TESTNET_LAUNCH = 34;

  // Macro
  INTEREST_RATE = 40;
  INFLATION = 41;
  GEOPOLITICAL = 42;
  MONETARY_POLICY = 43;
  FISCAL_POLICY = 44;

  // Market Structure
  ETF_APPROVAL = 50;
  ETF_REJECTION = 51;
  INSTITUTIONAL = 52;
  WHALE_MOVEMENT = 53;
  EXCHANGE_RESERVE = 54;
}

message DedupedNewsEvent {
  string canonical_event_id = 1;
  EventType primary_event_type = 2;
  string primary_coin = 3;
  string headline = 4;
  repeated string source_names = 5;
  int32 source_count = 6;
  double impact_score = 7;
  double sentiment_polarity = 8;
  double sentiment_confidence = 9;
  bool is_breaking = 10;
  google.protobuf.Timestamp first_published_at = 11;
  google.protobuf.Timestamp last_updated_at = 12;
}

message ScoredNewsEvent {
  string canonical_event_id = 1;
  EventType primary_event_type = 2;
  string primary_coin = 3;
  string headline = 4;
  int32 source_count = 5;
  repeated string sources = 6;
  double impact_score = 7;
  double sentiment_polarity = 8;
  double sentiment_confidence = 9;
  bool is_breaking = 10;
  double news_impact_score = 11;  // 0-1 for opportunity scoring
  google.protobuf.Timestamp detected_at = 12;
}

message BreakingNewsAlert {
  string canonical_event_id = 1;
  EventType event_type = 2;
  string primary_coin = 3;
  int32 source_count = 4;
  repeated string sources = 5;
  double impact_score = 6;
  double sentiment_polarity = 7;
  int64 detection_latency_ms = 8;
  string headline = 9;
  google.protobuf.Timestamp timestamp = 10;
}
```

## Configuration

```yaml
news_analysis:
  # Global settings
  enabled: true
  default_language: "en"

  # Feed configuration (see Data Sources section for full config)
  feeds:
    poll_jitter_percent: 20          # Add 0-20% jitter to avoid thundering herd
    max_article_age_hours: 24        # Ignore articles older than 24h
    max_body_length_chars: 10000     # Truncate long articles

  # NLP pipeline
  nlp:
    entity_extraction:
      coin_dictionary_path: "/config/coin_dictionary.json"
      ner_model: "en_core_web_sm"    # spaCy model for people/orgs
    event_classification:
      keyword_confidence_threshold: 0.85   # Skip LLM if keyword > threshold
      llm_model: "gpt-4o-mini"            # For ambiguous classification
      llm_timeout_ms: 2000
      llm_max_retries: 1
    sentiment:
      event_weight: 0.6                    # Weight of event-type default sentiment
      keyword_weight: 0.4                  # Weight of article keyword sentiment
    impact_scoring:
      fatigue_window_hours: 24
      fatigue_decay_per_event: 0.2
      fatigue_floor: 0.4

  # Deduplication
  dedup:
    minhash_num_hashes: 128
    similarity_threshold: 0.6
    time_window_minutes: 30
    title_cosine_threshold: 0.7
    cluster_ttl_hours: 4                   # Clean up old clusters

  # Breaking news detection
  breaking:
    source_threshold: 3                    # Sources needed for breaking
    time_window_minutes: 5                 # Window to count sources
    impact_boost_factor: 1.3               # Amplify impact for breaking

  # Integration with opportunity scoring
  integration:
    weight_in_opportunity_score: 0.12      # 12% weight
    suppress_threshold: 7.0                # Impact >= 7 suppresses BUY
    suppress_window_minutes: 30
    independent_signal_threshold: 7.0      # Impact >= 7 generates news signal
    independent_signal_min_confidence: 0.6
    time_decay_halflife_minutes: 120       # Impact halves every 2 hours

  # Historical validation
  validation:
    measurement_windows:
      - "5m"
      - "15m"
      - "1h"
      - "4h"
      - "24h"
    direction_threshold: 0.005             # 0.5% move counts as directional
    report_interval_hours: 24              # Daily accuracy report

  # Kafka
  kafka:
    bootstrap_servers: "${KAFKA_BOOTSTRAP}"
    topics:
      raw_articles: "news.raw-articles"
      extracted_events: "news.extracted-events"
      deduped_events: "news.deduped-events"
      scored_events: "news.scored-events"
      breaking_alerts: "news.breaking-alerts"
    consumer_group: "news-analysis"

  # Redis
  redis:
    event_cache_ttl_hours: 4
    breaking_alert_ttl_minutes: 30

  # Updated opportunity scoring weights (with news factor)
  opportunity_scoring:
    weights:
      confidence: 0.22
      expected_return: 0.27
      consensus: 0.18
      volatility: 0.13
      freshness: 0.08
      news_impact: 0.12
```

## Constraints

- **Latency**: End-to-end from publication to opportunity score update must be < 60 seconds.
- **Throughput**: Must handle 500+ articles per hour across all sources without backpressure.
- **Deduplication accuracy**: False duplicate rate < 2% (articles incorrectly merged).
- **Classification accuracy**: Event type classification accuracy > 85% measured on labeled test set.
- **Availability**: Feed ingestion must tolerate individual source outages without system degradation.
- **Cost**: LLM classification calls (for ambiguous articles) must stay under $50/day at 500 articles/day.
- **Storage**: Raw articles retained 7 days; events retained 90 days; outcomes retained indefinitely.
- **Determinism**: Same article processed twice must produce the same extracted event (excluding timestamps).
- **Language**: English-only for v1. Non-English articles are dropped with a logged metric.
- **Rate limits**: Must respect per-source API rate limits. Circuit breaker per source on repeated 429s.

## Non-Goals

- **Trading execution**: This system produces signals and scores, not trade execution.
- **Social media analysis**: Twitter/X, Reddit, and Telegram are covered by the separate Social Media Sentiment spec.
- **On-chain data**: Whale movements and on-chain metrics are covered by the Whale Wallet Monitoring spec.
- **Sentiment indices**: Aggregated market sentiment indices (Fear & Greed) are covered by the Sentiment Indices spec.
- **Multilingual NLP**: Non-English news analysis is deferred to a future version.
- **Paywall bypass**: We only ingest freely accessible content or content available via paid API subscriptions.
- **Custom LLM training**: v1 uses a pre-trained LLM for classification; fine-tuning is a future optimization.
- **Real-time video/audio**: Parsing live streams, podcasts, or video content is out of scope.

## Acceptance Criteria

- [ ] Feed ingestion service polls 10+ configured sources on schedule
- [ ] Feed health monitor alerts when a source produces no articles for 15+ minutes
- [ ] Entity extraction correctly identifies coin mentions, people, and organizations
- [ ] Event classification maps articles to taxonomy with > 85% accuracy
- [ ] Impact magnitude scoring produces scores 1-10 with source credibility weighting
- [ ] Sentiment analysis produces polarity (-1 to +1) per affected coin
- [ ] Duplicate detection merges paraphrased articles about the same event (< 2% false merge rate)
- [ ] Breaking news detection fires alert when 3+ sources report same event within 5 minutes
- [ ] Breaking news detection latency is < 60 seconds from first source publication
- [ ] `news_impact_score` (0-1) computed and available for opportunity scoring
- [ ] Opportunity score formula updated with 12% news_impact weight
- [ ] BUY signals suppressed when impact >= 7 bearish event is active for the coin
- [ ] Independent news event signals generated for impact >= 7 events
- [ ] Historical validator records price changes at t+5m, t+15m, t+1h, t+4h, t+24h
- [ ] Model accuracy metrics available via Prometheus (direction accuracy by event type and window)
- [ ] All Kafka topics created with correct partitioning and retention
- [ ] Proto definitions compile and integrate with existing Java/Kotlin codebase
- [ ] PostgreSQL schema deployed via migration
- [ ] Configuration externalized via YAML and environment variables
- [ ] Feed source credentials stored in Kubernetes secrets, not in config

## File Structure

```
src/main/java/com/verlumen/tradestream/news/
|-- NewsModule.java                          # Guice module
|-- ingestion/
|   |-- NewsFeedIngestionPipeline.java       # Beam pipeline
|   |-- RssFetcherFn.java                   # RSS DoFn
|   |-- RestApiFetcherFn.java               # REST API DoFn
|   |-- FeedHealthMonitor.java              # Feed staleness detection
|   |-- RawArticleSerializer.java           # Kafka serializer
|   `-- BUILD
|-- extraction/
|   |-- NewsEntityExtractor.java            # NER + coin extraction
|   |-- CoinDictionary.java                 # Ticker <-> name mapping
|   `-- BUILD
|-- classification/
|   |-- NewsEventClassifier.java            # Two-stage classifier
|   |-- KeywordClassifier.java              # Fast keyword matching
|   |-- LlmClassifier.java                  # LLM-based fallback
|   `-- BUILD
|-- scoring/
|   |-- ImpactScorer.java                   # Impact magnitude 1-10
|   |-- NewsSentimentAnalyzer.java          # Sentiment polarity
|   |-- NewsImpactScoreCalculator.java      # news_impact_score 0-1
|   `-- BUILD
|-- dedup/
|   |-- ArticleDeduplicator.java            # MinHash LSH dedup
|   |-- MinHashIndex.java                   # LSH index
|   |-- EventClusterStore.java              # Canonical event clusters
|   `-- BUILD
|-- breaking/
|   |-- BreakingNewsDetector.java           # Flink CEP detection
|   `-- BUILD
|-- signal/
|   |-- NewsSignalGate.java                 # BUY suppression gate
|   |-- NewsSignalGenerator.java            # Independent news signals
|   `-- BUILD
|-- validation/
|   |-- NewsImpactValidator.java            # Historical price correlation
|   `-- BUILD
|-- config/
|   |-- NewsConfig.java                     # Configuration POJO
|   |-- FeedSourceConfig.java               # Per-source config
|   `-- BUILD
protos/
|-- news_events.proto                       # Proto definitions
|-- BUILD                                   # Proto build targets
src/test/java/com/verlumen/tradestream/news/
|-- extraction/
|   |-- NewsEntityExtractorTest.java
|   `-- BUILD
|-- classification/
|   |-- KeywordClassifierTest.java
|   |-- NewsEventClassifierTest.java
|   `-- BUILD
|-- scoring/
|   |-- ImpactScorerTest.java
|   |-- NewsImpactScoreCalculatorTest.java
|   `-- BUILD
|-- dedup/
|   |-- ArticleDeduplicatorTest.java
|   `-- BUILD
|-- breaking/
|   |-- BreakingNewsDetectorTest.java
|   `-- BUILD
|-- signal/
|   |-- NewsSignalGateTest.java
|   |-- NewsSignalGeneratorTest.java
|   `-- BUILD
|-- validation/
|   |-- NewsImpactValidatorTest.java
|   `-- BUILD
charts/tradestream/templates/
|-- news-ingestion-deployment.yaml
|-- news-processor-deployment.yaml
|-- news-configmap.yaml
migrations/
|-- V020__create_news_events_tables.sql
config/
|-- coin_dictionary.json                    # Coin name/ticker mapping
|-- news_config.yaml                        # Default configuration
```

## Notes

- **LLM cost control**: The two-stage classification approach (keyword first, LLM fallback) reduces LLM calls by ~80%. At 500 articles/day with 20% needing LLM, that is ~100 LLM calls/day at ~$0.01 each = ~$1/day for classification.

- **Bootstrapping the impact model**: Initial impact magnitudes are based on the event taxonomy defaults. After 30 days of historical validation data, the system can recalibrate base impact values per event type based on observed price correlations. This recalibration is manual for v1 (review accuracy dashboard, adjust config).

- **Interaction with other external signals**: The `news_impact_score` is one of potentially several external signal factors. The umbrella External Signals spec defines how multiple external factors (news, social sentiment, whale tracking, sentiment indices) are combined. The 12% weight for news may be adjusted as additional external signals are added.

- **Feed source redundancy**: If a P0 source becomes permanently unavailable, the system continues to function with reduced coverage. Feed health alerts notify operators to investigate and potentially add replacement sources.

- **Flink checkpoint configuration**: The breaking news detector uses Flink state with checkpointing enabled (interval: 60s, mode: EXACTLY_ONCE) to ensure no events are lost during Flink restarts.

- **Coin dictionary maintenance**: The `coin_dictionary.json` maps names to tickers (e.g., "bitcoin" -> "BTC"). This must be updated when new coins are added to the trading universe. Consider automating this from CoinGecko's API as a periodic batch job.
