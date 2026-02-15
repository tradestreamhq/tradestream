# Social Media Sentiment Analysis Specification

## Goal

Ingest social media data from multiple platforms, compute per-symbol sentiment scores in real-time, and feed a `social_sentiment_score` into the opportunity scoring formula so that trading signals reflect the crowd's conviction and emerging narrative shifts.

## Target Behavior

The system continuously monitors Twitter/X, Reddit, Telegram, and Discord for mentions of tracked trading symbols. Raw posts are processed through an NLP sentiment pipeline that produces a normalized, volume-weighted sentiment score per symbol. This score is published as a new factor in the opportunity scoring formula, complementing the existing technical-analysis-only approach with social signal data.

### Scoring Output

Each symbol receives a rolling `social_sentiment_score` (0.0 to 1.0) that represents:

| Score Range | Interpretation |
|-------------|----------------|
| 0.80 - 1.00 | Extreme bullish sentiment |
| 0.60 - 0.79 | Moderately bullish |
| 0.40 - 0.59 | Neutral / mixed |
| 0.20 - 0.39 | Moderately bearish |
| 0.00 - 0.19 | Extreme bearish sentiment |

The score is derived from three components:

1. **Polarity** (-1 to +1): Average sentiment of individual posts, weighted by engagement.
2. **Volume signal** (0 to 1): Relative mention volume compared to the 7-day rolling average. Spikes amplify the score; silence dampens it.
3. **Credibility weight** (0 to 1): Filters out bots, spam, and low-quality accounts to ensure signal integrity.

```python
def calculate_social_sentiment_score(
    polarity: float,          # -1.0 to +1.0, engagement-weighted average
    volume_ratio: float,      # current_mentions / 7d_avg_mentions
    credibility: float,       # 0.0 to 1.0, proportion of credible posts
) -> float:
    """
    Compute social sentiment score (0.0 - 1.0) for a symbol.

    Returns:
        Float between 0.0 and 1.0
    """
    # Normalize polarity from [-1, +1] to [0, 1]
    polarity_normalized = (polarity + 1) / 2

    # Volume multiplier: 1.0 at average volume, capped at 1.5 for 3x+ spikes
    volume_multiplier = min(1.0 + (volume_ratio - 1.0) * 0.25, 1.5)
    # Below-average volume dampens signal, floor at 0.5
    volume_multiplier = max(volume_multiplier, 0.5)

    # Weighted combination
    raw_score = (
        0.60 * polarity_normalized +
        0.25 * min(volume_ratio / 3.0, 1.0) +
        0.15 * credibility
    ) * volume_multiplier

    return round(max(0.0, min(1.0, raw_score)), 4)
```

**Example Calculations:**

| Scenario | Polarity | Volume Ratio | Credibility | Score |
|----------|----------|-------------|-------------|-------|
| Strong bullish viral spike | +0.7 | 4.2 | 0.85 | 0.89 |
| Moderate bullish, normal volume | +0.4 | 1.1 | 0.90 | 0.63 |
| Neutral, low volume | +0.05 | 0.3 | 0.80 | 0.28 |
| Bearish, high volume | -0.6 | 2.5 | 0.75 | 0.27 |
| Mixed, bot-heavy | +0.2 | 3.0 | 0.20 | 0.44 |

### Architecture

```
                    SOCIAL MEDIA SENTIMENT PIPELINE

  +-----------+  +-----------+  +-----------+  +-----------+
  | Twitter/X |  |  Reddit   |  | Telegram  |  |  Discord  |
  |  API v2   |  |   API     |  |  Scraper  |  |   Bot     |
  +-----------+  +-----------+  +-----------+  +-----------+
       |              |              |              |
       v              v              v              v
  +-----------------------------------------------------------+
  |              Kafka: social.raw.{platform}                  |
  |  (partitioned by symbol, one topic per platform)           |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |            INGESTION PROCESSOR (Beam/Flink)                |
  |                                                             |
  |  1. Normalize post schema across platforms                 |
  |  2. Extract symbol mentions ($BTC, #ETH, cashtags)        |
  |  3. Deduplicate (cross-platform, reposts, quote tweets)   |
  |  4. Assign ingestion timestamp                             |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |              Kafka: social.normalized                       |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |            SPAM / BOT FILTER (Beam/Flink)                  |
  |                                                             |
  |  1. Account age check (< 30 days = suspect)               |
  |  2. Follower-to-following ratio                            |
  |  3. Post frequency anomaly detection                       |
  |  4. Duplicate content fingerprinting (SimHash)             |
  |  5. Known bot list lookup (Redis set)                      |
  |  6. Assign credibility_score (0-1) per post               |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |              Kafka: social.filtered                         |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |            SENTIMENT SCORER (Beam/Flink)                    |
  |                                                             |
  |  1. Run FinBERT inference on post text                     |
  |  2. Apply engagement weighting (likes, retweets, upvotes) |
  |  3. Compute per-post polarity (-1 to +1)                  |
  |  4. Write scored posts to InfluxDB                         |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |              Kafka: social.scored                           |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |            AGGREGATOR (Beam/Flink)                          |
  |                                                             |
  |  1. 5-min tumbling window aggregation per symbol           |
  |  2. Compute volume-weighted polarity                       |
  |  3. Compute volume ratio vs 7d rolling average             |
  |  4. Compute average credibility for window                 |
  |  5. Calculate social_sentiment_score                       |
  |  6. Viral spike detection (60s sliding window)             |
  |  7. Write aggregated score to PostgreSQL + Redis           |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |              Redis: social:sentiment:{symbol}              |
  |              PostgreSQL: social_sentiment_scores            |
  |              InfluxDB: social_sentiment_timeseries          |
  +-----------------------------------------------------------+
       |
       v
  +-----------------------------------------------------------+
  |            OPPORTUNITY SCORER AGENT                         |
  |                                                             |
  |  Reads social_sentiment_score from Redis                   |
  |  Plugs into modified opportunity scoring formula           |
  +-----------------------------------------------------------+
```

### Viral Spike Detection

Breaking viral posts must be detected within 60 seconds. A dedicated sliding window runs in parallel with the 5-minute aggregation:

```python
class ViralSpikeDetector:
    """
    Detects sudden spikes in social mention volume.

    Uses a 60-second sliding window compared against the
    trailing 1-hour baseline to identify viral events.
    """

    def __init__(self, config: ViralSpikeConfig):
        self.spike_threshold = config.spike_threshold  # e.g., 5.0 = 5x baseline
        self.min_mentions = config.min_mentions        # e.g., 10 mentions in window
        self.cooldown_seconds = config.cooldown_seconds  # e.g., 300 = 5 min

    def detect(
        self,
        symbol: str,
        window_60s_count: int,
        baseline_1h_rate: float,  # mentions per 60 seconds, averaged over 1 hour
    ) -> Optional[ViralSpike]:
        """
        Detect viral spike for a symbol.

        Returns ViralSpike if spike detected, None otherwise.
        """
        if window_60s_count < self.min_mentions:
            return None

        if baseline_1h_rate <= 0:
            baseline_1h_rate = 1.0  # Prevent division by zero

        spike_ratio = window_60s_count / baseline_1h_rate

        if spike_ratio >= self.spike_threshold:
            return ViralSpike(
                symbol=symbol,
                spike_ratio=spike_ratio,
                mention_count=window_60s_count,
                baseline_rate=baseline_1h_rate,
                detected_at=datetime.utcnow(),
            )

        return None
```

When a viral spike is detected:
1. Immediately publish to `Kafka: social.viral-alerts`
2. Trigger an out-of-cycle sentiment re-aggregation for the symbol
3. Emit `viral_spike_detected` metric
4. Optionally notify the reporting agent for urgent alerts

## Data Sources

### Primary: Direct API Access

| Platform | API | Endpoints Used | Rate Limits | Monthly Cost |
|----------|-----|----------------|-------------|-------------|
| **Twitter/X** | v2 API (Basic tier) | Filtered stream, Recent search, User lookup | 500K tweets/month (Basic), 10M (Pro) | $100/mo (Basic), $5,000/mo (Pro) |
| **Reddit** | Reddit API (free tier) | /r/cryptocurrency, /r/bitcoin, /r/ethtrader /new, /r/wallstreetbets | 100 requests/min (OAuth) | Free (OAuth app) |
| **Telegram** | Telethon (MTProto) | Public channel message history | 30 requests/sec per account | Free (API access) |
| **Discord** | Discord.js bot | Public server message events | 50 requests/sec per bot | Free (bot account) |

### Twitter/X Integration

```python
class TwitterIngester:
    """
    Ingest tweets via Twitter API v2.

    Uses filtered stream for real-time cashtag tracking
    and recent search for backfill/catch-up.
    """

    def __init__(self, config: TwitterConfig):
        self.bearer_token = config.bearer_token
        self.stream_rules = self._build_rules(config.tracked_symbols)

    def _build_rules(self, symbols: list[str]) -> list[dict]:
        """
        Build Twitter filtered stream rules for tracked symbols.

        Uses cashtags ($BTC, $ETH) and common variations.
        """
        rules = []
        for symbol in symbols:
            ticker = symbol.split("/")[0]  # "ETH/USD" -> "ETH"
            rule = (
                f"(${ticker} OR #{ticker} OR {ticker.lower()}) "
                f"lang:en -is:retweet -is:reply"
            )
            rules.append({"value": rule, "tag": f"symbol:{ticker}"})
        return rules

    async def start_stream(self):
        """Connect to filtered stream and produce to Kafka."""
        async for tweet in self.client.filtered_stream(
            tweet_fields=["created_at", "public_metrics", "author_id", "lang"],
            user_fields=["created_at", "public_metrics", "verified"],
            expansions=["author_id"],
        ):
            normalized = self._normalize(tweet)
            await self.kafka_producer.send(
                topic=f"social.raw.twitter",
                key=normalized.symbol,
                value=normalized.to_json(),
            )
```

### Reddit Integration

```python
class RedditIngester:
    """
    Ingest posts and comments from cryptocurrency subreddits.

    Polls /new endpoints every 30 seconds for each tracked subreddit.
    """

    SUBREDDITS = [
        "cryptocurrency",
        "bitcoin",
        "ethtrader",
        "CryptoMarkets",
        "SatoshiStreetBets",
        "wallstreetbets",
    ]

    async def poll_subreddit(self, subreddit: str):
        """Fetch new posts and comments from subreddit."""
        async for submission in self.reddit.subreddit(subreddit).new(limit=100):
            if self._mentions_tracked_symbol(submission.title + submission.selftext):
                normalized = self._normalize_post(submission)
                await self.kafka_producer.send(
                    topic="social.raw.reddit",
                    key=normalized.symbol,
                    value=normalized.to_json(),
                )

        # Also fetch hot comments for engagement-weighted sentiment
        async for comment in self.reddit.subreddit(subreddit).comments(limit=200):
            if self._mentions_tracked_symbol(comment.body):
                normalized = self._normalize_comment(comment)
                await self.kafka_producer.send(
                    topic="social.raw.reddit",
                    key=normalized.symbol,
                    value=normalized.to_json(),
                )
```

### Telegram Integration

```python
class TelegramIngester:
    """
    Ingest messages from public Telegram channels.

    Uses Telethon (MTProto client) for real-time message events.
    """

    CHANNELS = [
        "WhaleCalls",
        "CryptoSignalsIO",
        "CoinGeckoAlerts",
        "AltcoinBuzz",
        "CryptoCapitalVenture",
    ]

    async def listen_channel(self, channel: str):
        """Listen for new messages in a public Telegram channel."""
        entity = await self.client.get_entity(channel)
        async for message in self.client.iter_messages(entity, limit=None):
            if message.date < self.last_seen[channel]:
                break
            if self._mentions_tracked_symbol(message.text or ""):
                normalized = self._normalize(message, channel)
                await self.kafka_producer.send(
                    topic="social.raw.telegram",
                    key=normalized.symbol,
                    value=normalized.to_json(),
                )
```

### Alternative: Aggregator APIs

For faster time-to-value or if direct API costs are prohibitive, use social data aggregators:

| Provider | Data | API Cost | Advantage |
|----------|------|----------|-----------|
| **LunarCrush** | Social metrics, sentiment, engagement | $200-500/mo | Pre-computed sentiment, covers Twitter/Reddit/YouTube |
| **Santiment** | Social volume, sentiment, dev activity | $250-1,000/mo | Includes on-chain + social, historical data |
| **The TIE** | Real-time social sentiment, NLP-scored | Custom pricing | Institutional-grade, covers 900+ coins |
| **CryptoCompare** | Social stats API | Free tier available | Basic social metrics, easy integration |

**Recommendation**: Start with **LunarCrush** for MVP (pre-computed sentiment reduces NLP infrastructure needs), then migrate to direct API ingestion for cost savings and customization as volume grows.

```python
class LunarCrushIngester:
    """
    Fallback ingester using LunarCrush pre-computed sentiment.

    Useful for MVP or when direct API rate limits are insufficient.
    """

    async def fetch_sentiment(self, symbol: str) -> SocialMetrics:
        """Fetch pre-computed social metrics from LunarCrush."""
        response = await self.client.get(
            f"/v2/assets/{symbol}",
            params={"data": "social"},
        )
        data = response.json()["data"]

        return SocialMetrics(
            symbol=symbol,
            sentiment_score=data["sentiment"] / 5.0,  # Normalize 1-5 to 0-1
            social_volume=data["social_volume"],
            social_volume_change_24h=data["social_volume_change_24h"],
            bullish_sentiment=data["bullish_sentiment"],
            bearish_sentiment=data["bearish_sentiment"],
            galaxy_score=data["galaxy_score"],
            fetched_at=datetime.utcnow(),
        )
```

## Implementation

### Normalized Post Schema

All platforms produce posts in a unified format before entering the sentiment pipeline:

```protobuf
// protos/social_sentiment.proto

syntax = "proto3";
package com.verlumen.tradestream.social;

message SocialPost {
  string post_id = 1;                    // Unique ID: "{platform}:{native_id}"
  string platform = 2;                   // twitter, reddit, telegram, discord
  string symbol = 3;                     // Extracted symbol (e.g., "ETH")
  string text = 4;                       // Post content (max 1000 chars)
  string author_id = 5;                  // Platform-specific author ID
  int64 timestamp_ms = 6;               // Post creation time (epoch ms)
  EngagementMetrics engagement = 7;
  AuthorMetrics author = 8;
  string source_url = 9;                 // Original post URL
  string language = 10;                  // ISO 639-1 code (e.g., "en")

  message EngagementMetrics {
    int32 likes = 1;
    int32 reposts = 2;                   // retweets, shares, forwards
    int32 replies = 3;
    int32 views = 4;                     // impressions, if available
  }

  message AuthorMetrics {
    int32 followers = 1;
    int32 following = 2;
    int64 account_created_ms = 3;
    bool verified = 4;
    int32 total_posts = 5;
  }
}

message ScoredPost {
  SocialPost post = 1;
  float polarity = 2;                    // -1.0 to +1.0
  float confidence = 3;                  // Model confidence 0.0 to 1.0
  float credibility_score = 4;           // 0.0 to 1.0
  float engagement_weight = 5;           // Normalized engagement score
  string model_version = 6;             // e.g., "finbert-v1.2"
}

message SentimentAggregate {
  string symbol = 1;
  int64 window_start_ms = 2;
  int64 window_end_ms = 3;
  float polarity = 4;                    // Volume-weighted avg polarity
  float volume_ratio = 5;               // vs 7-day rolling average
  float credibility = 6;                // Avg credibility of posts in window
  float social_sentiment_score = 7;     // Final 0-1 score
  int32 post_count = 8;
  int32 unique_authors = 9;
  map<string, int32> platform_breakdown = 10;  // posts per platform
  bool viral_spike = 11;
  float spike_ratio = 12;
}
```

### Sentiment Model: FinBERT

**Model Selection Rationale:**

| Model | Pros | Cons | Recommendation |
|-------|------|------|----------------|
| **FinBERT** | Pre-trained on financial text, fast inference (~5ms/post), well-tested | May miss crypto slang, smaller context window | **Primary model** |
| **Custom fine-tuned BERT** | Crypto-specific vocabulary, highest accuracy | Training data needed, maintenance overhead | Phase 2 |
| **LLM-based (GPT-4/Claude)** | Best understanding of context and sarcasm | Slow (~500ms/post), expensive at scale | Viral spike analysis only |
| **VADER + TextBlob** | Zero latency, no GPU needed | Poor on financial/crypto text, no context | Fallback only |

**Primary choice: FinBERT** (ProsusAI/finbert) with a crypto-specific vocabulary extension.

```python
class FinBERTScorer:
    """
    Score post sentiment using FinBERT.

    Optimized for batch inference with ONNX runtime
    for sub-5ms per-post latency.
    """

    def __init__(self, config: SentimentModelConfig):
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = ORTModelForSequenceClassification.from_pretrained(
            config.model_path,  # ONNX-exported FinBERT
        )
        self.batch_size = config.batch_size  # 32 posts per batch
        self.max_length = config.max_length  # 128 tokens

    def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        """
        Score a batch of post texts.

        Returns list of (polarity, confidence) tuples.
        polarity: -1.0 (bearish) to +1.0 (bullish)
        confidence: 0.0 to 1.0 (model certainty)
        """
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )

        outputs = self.model(**inputs)
        probabilities = softmax(outputs.logits, axis=1)

        results = []
        for probs in probabilities:
            # FinBERT outputs: [negative, neutral, positive]
            neg, neu, pos = probs[0], probs[1], probs[2]

            # Polarity: positive probability minus negative probability
            polarity = float(pos - neg)

            # Confidence: how sure the model is (1 - neutral probability)
            confidence = float(1.0 - neu)

            results.append(SentimentResult(
                polarity=polarity,
                confidence=confidence,
            ))

        return results
```

### Spam and Bot Filtering

```python
class SpamBotFilter:
    """
    Filter spam and bot posts to maintain sentiment signal quality.

    Each post receives a credibility_score (0.0 to 1.0).
    Posts below the threshold are discarded from aggregation.
    """

    def __init__(self, config: SpamFilterConfig):
        self.min_account_age_days = config.min_account_age_days  # 30
        self.min_credibility = config.min_credibility_threshold  # 0.3
        self.known_bots = config.known_bot_set  # Redis set lookup
        self.simhash_index = SimHashIndex()  # Duplicate content detection

    def compute_credibility(self, post: SocialPost) -> float:
        """
        Compute credibility score for a post.

        Factors:
        - Account age (0-0.25)
        - Follower ratio (0-0.25)
        - Post originality (0-0.25)
        - Platform verification (0-0.25)
        """
        scores = []

        # Account age: 0 if < 30 days, ramps to 1.0 at 365 days
        account_age_days = (
            time.time() * 1000 - post.author.account_created_ms
        ) / (86400 * 1000)
        age_score = min(
            max(0, (account_age_days - self.min_account_age_days) / 335),
            1.0,
        )
        scores.append(0.25 * age_score)

        # Follower ratio: penalize accounts with high following/low followers
        if post.author.following > 0:
            ratio = post.author.followers / post.author.following
            ratio_score = min(ratio / 2.0, 1.0)  # 2:1 ratio = full score
        else:
            ratio_score = 0.5  # Unknown
        scores.append(0.25 * ratio_score)

        # Content originality: SimHash duplicate detection
        content_hash = self.simhash_index.compute(post.text)
        is_duplicate = self.simhash_index.find_near_duplicate(
            content_hash, threshold=3
        )
        originality_score = 0.0 if is_duplicate else 1.0
        scores.append(0.25 * originality_score)

        # Verification / account quality
        verification_score = 1.0 if post.author.verified else 0.5
        scores.append(0.25 * verification_score)

        credibility = sum(scores)

        # Known bot penalty: set credibility to 0
        if self.known_bots.contains(post.author_id):
            credibility = 0.0

        return round(credibility, 4)
```

### Engagement Weighting

Posts with higher engagement carry more weight in the polarity aggregation:

```python
def compute_engagement_weight(engagement: EngagementMetrics) -> float:
    """
    Compute engagement-based weight for a post.

    Uses log-scale to prevent viral posts from dominating.
    Returns weight between 0.1 and 10.0.
    """
    raw_engagement = (
        engagement.likes * 1.0 +
        engagement.reposts * 2.0 +   # Reposts signal stronger conviction
        engagement.replies * 0.5 +    # Replies indicate discussion, not agreement
        engagement.views * 0.001      # Views are cheap, low weight
    )

    # Log scale: prevents single viral post from dominating
    # +1 to handle zero engagement gracefully
    weight = math.log2(raw_engagement + 1) + 0.1

    # Cap at 10x to prevent any single post from overwhelming
    return min(weight, 10.0)
```

### Aggregation Pipeline (Apache Beam)

```python
class SentimentAggregationPipeline:
    """
    Apache Beam pipeline for real-time sentiment aggregation.

    Runs on Flink runner with 5-minute tumbling windows
    and a parallel 60-second sliding window for viral detection.
    """

    def build_pipeline(self, pipeline: beam.Pipeline):
        scored_posts = (
            pipeline
            | "ReadFromKafka" >> beam.io.ReadFromKafka(
                consumer_config=self.kafka_config,
                topics=["social.scored"],
            )
            | "ParseScoredPost" >> beam.Map(self._parse_scored_post)
            | "FilterLowCredibility" >> beam.Filter(
                lambda p: p.credibility_score >= self.min_credibility
            )
        )

        # 5-minute tumbling window aggregation
        (
            scored_posts
            | "KeyBySymbol" >> beam.Map(lambda p: (p.post.symbol, p))
            | "Window5Min" >> beam.WindowInto(
                beam.window.FixedWindows(300)  # 5 minutes
            )
            | "Aggregate" >> beam.CombinePerKey(SentimentCombineFn())
            | "ComputeScore" >> beam.Map(self._compute_sentiment_score)
            | "WriteToPostgres" >> beam.ParDo(WriteToPostgresFn())
            | "WriteToRedis" >> beam.ParDo(WriteToRedisFn())
            | "WriteToInfluxDB" >> beam.ParDo(WriteToInfluxDBFn())
        )

        # 60-second sliding window for viral spike detection
        (
            scored_posts
            | "KeyBySymbolViral" >> beam.Map(lambda p: (p.post.symbol, p))
            | "Window60s" >> beam.WindowInto(
                beam.window.SlidingWindows(60, 10)  # 60s window, 10s slide
            )
            | "CountPerWindow" >> beam.CombinePerKey(CountCombineFn())
            | "DetectSpike" >> beam.ParDo(ViralSpikeDetectorFn())
            | "PublishAlerts" >> beam.ParDo(PublishViralAlertFn())
        )


class SentimentCombineFn(beam.CombineFn):
    """Combine scored posts into an aggregate sentiment."""

    def create_accumulator(self):
        return {
            "weighted_polarity_sum": 0.0,
            "total_weight": 0.0,
            "credibility_sum": 0.0,
            "post_count": 0,
            "unique_authors": set(),
            "platform_counts": {},
        }

    def add_input(self, accumulator, scored_post):
        weight = scored_post.engagement_weight * scored_post.credibility_score
        accumulator["weighted_polarity_sum"] += scored_post.polarity * weight
        accumulator["total_weight"] += weight
        accumulator["credibility_sum"] += scored_post.credibility_score
        accumulator["post_count"] += 1
        accumulator["unique_authors"].add(scored_post.post.author_id)
        platform = scored_post.post.platform
        accumulator["platform_counts"][platform] = (
            accumulator["platform_counts"].get(platform, 0) + 1
        )
        return accumulator

    def extract_output(self, accumulator):
        if accumulator["total_weight"] == 0:
            return None

        return {
            "polarity": (
                accumulator["weighted_polarity_sum"]
                / accumulator["total_weight"]
            ),
            "credibility": (
                accumulator["credibility_sum"]
                / accumulator["post_count"]
            ),
            "post_count": accumulator["post_count"],
            "unique_authors": len(accumulator["unique_authors"]),
            "platform_breakdown": accumulator["platform_counts"],
        }
```

### Volume Ratio Computation

The volume ratio compares the current window's mention count against a 7-day rolling average, stored in InfluxDB:

```python
class VolumeRatioComputer:
    """Compute mention volume ratio against 7-day rolling average."""

    def __init__(self, influxdb_client):
        self.influx = influxdb_client

    async def compute(self, symbol: str, current_count: int) -> float:
        """
        Compute volume ratio for a symbol.

        Returns ratio of current 5-min count to 7-day average 5-min count.
        """
        query = f'''
        from(bucket: "social_sentiment")
          |> range(start: -7d)
          |> filter(fn: (r) => r._measurement == "sentiment_aggregate")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> filter(fn: (r) => r._field == "post_count")
          |> mean()
        '''
        result = await self.influx.query(query)
        avg_count = result[0].records[0].get_value() if result else 1.0

        if avg_count <= 0:
            avg_count = 1.0  # Prevent division by zero

        return current_count / avg_count
```

## Integration with Opportunity Scoring

### Modified Opportunity Score Formula

The `social_sentiment_score` is added as a sixth factor. Weights are rebalanced to sum to 100%:

**Previous weights:**

| Factor | Old Weight |
|--------|-----------|
| Confidence | 25% |
| Expected Return | 30% |
| Strategy Consensus | 20% |
| Volatility | 15% |
| Freshness | 10% |

**New weights (with social sentiment):**

| Factor | New Weight | Change | Rationale |
|--------|-----------|--------|-----------|
| Confidence | 22% | -3% | Slight reduction; social data adds context |
| Expected Return | 27% | -3% | Still dominant factor, slight trim |
| Strategy Consensus | 18% | -2% | Social sentiment partially overlaps consensus |
| Volatility | 13% | -2% | Minor trim; social can explain volatility |
| Freshness | 10% | 0% | Unchanged; time decay remains important |
| **Social Sentiment** | **10%** | **+10%** | New factor; conservative weight for initial rollout |

```python
def calculate_opportunity_score(
    confidence: float,           # 0.0 - 1.0
    expected_return: float,      # percentage, e.g., 0.032 for 3.2%
    return_stddev: float,        # standard deviation of strategy returns
    consensus_pct: float,        # 0.0 - 1.0
    volatility: float,           # hourly volatility, e.g., 0.021
    minutes_ago: int,            # signal age in minutes
    social_sentiment: float,     # 0.0 - 1.0 (NEW)
    market_regime: str = "normal"
) -> float:
    """
    Calculate opportunity score (0-100) for a trading signal.

    Includes social sentiment as a new scoring factor.

    Returns:
        Float between 0 and 100
    """
    caps = get_regime_adjusted_caps(market_regime)

    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)

    volatility_score = min(volatility / caps.max_volatility, 1.0)

    freshness_score = max(0, 1 - (minutes_ago / 60))

    # Weighted sum (updated weights)
    opportunity_score = (
        0.22 * confidence +
        0.27 * return_score +
        0.18 * consensus_pct +
        0.13 * volatility_score +
        0.10 * freshness_score +
        0.10 * social_sentiment        # NEW FACTOR
    ) * 100

    return round(opportunity_score, 1)
```

### Scored Signal Format (Updated)

```json
{
  "signal_id": "sig-abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "opportunity_score": 89.2,
  "opportunity_score_cached_at": "2025-02-01T12:34:56Z",
  "opportunity_tier": "HOT",
  "market_regime": "normal",
  "opportunity_factors": {
    "confidence": { "value": 0.82, "contribution": 18.0 },
    "expected_return": {
      "value": 0.032,
      "stddev": 0.015,
      "risk_adjusted": 0.028,
      "contribution": 27.0
    },
    "consensus": { "value": 0.80, "contribution": 14.4 },
    "volatility": {
      "value": 0.021,
      "percentile": 0.65,
      "contribution": 9.1
    },
    "freshness": { "value": 0, "contribution": 10.0, "cached": true },
    "social_sentiment": {
      "value": 0.78,
      "polarity": 0.56,
      "volume_ratio": 2.1,
      "credibility": 0.82,
      "post_count_5min": 47,
      "viral_spike": false,
      "contribution": 7.8
    }
  },
  "timestamp": "2025-02-01T12:34:56Z"
}
```

### Score Breakdown Display (Updated)

```
OPPORTUNITY SCORE: 89

Confidence         82%    ████████░░    +18.0 pts
Expected Return    +3.2%  ██████████    +27.0 pts  (risk-adjusted)
Strategy Consensus 80%    ████████░░    +14.4 pts
Volatility         2.1%   ███████░░░    +9.1 pts   (regime: normal)
Freshness          0m     ██████████    +10.0 pts  (cached)
Social Sentiment   78%    ████████░░    +7.8 pts   (47 posts, 2.1x volume)
                          ─────────────────────
                          Total: 89.2 pts  (was 87.0 without social)
```

### MCP Tool for Opportunity Scorer

The Opportunity Scorer agent reads social sentiment via a new MCP tool:

```python
# In sentiment-mcp server

@mcp_tool("get_social_sentiment")
async def get_social_sentiment(symbol: str) -> dict:
    """
    Get current social sentiment score for a symbol.

    Reads from Redis cache (updated every 5 minutes by aggregation pipeline).
    Falls back to PostgreSQL if Redis is unavailable.
    """
    # Try Redis first (most recent)
    cached = await redis.get(f"social:sentiment:{symbol}")
    if cached:
        return json.loads(cached)

    # Fallback to PostgreSQL (slightly delayed)
    row = await postgres.fetchone(
        "SELECT * FROM social_sentiment_scores "
        "WHERE symbol = $1 ORDER BY window_end DESC LIMIT 1",
        symbol,
    )
    if row:
        return {
            "symbol": symbol,
            "social_sentiment_score": row["social_sentiment_score"],
            "polarity": row["polarity"],
            "volume_ratio": row["volume_ratio"],
            "credibility": row["credibility"],
            "post_count": row["post_count"],
            "viral_spike": row["viral_spike"],
            "window_end": row["window_end"].isoformat(),
        }

    # No data available
    return {
        "symbol": symbol,
        "social_sentiment_score": 0.5,  # Neutral default
        "data_available": False,
    }
```

## Storage

### InfluxDB: Time-Series Sentiment Data

```
Bucket: social_sentiment

Measurements:
  - scored_posts:
      tags: symbol, platform, model_version
      fields: polarity (float), confidence (float), credibility_score (float),
              engagement_weight (float)
      timestamp: post creation time

  - sentiment_aggregate:
      tags: symbol
      fields: polarity (float), volume_ratio (float), credibility (float),
              social_sentiment_score (float), post_count (int),
              unique_authors (int), viral_spike (bool)
      timestamp: window end time

  - viral_spikes:
      tags: symbol
      fields: spike_ratio (float), mention_count (int),
              baseline_rate (float)
      timestamp: detection time

Retention policies:
  - scored_posts: 7 days (raw post-level data)
  - sentiment_aggregate: 90 days (5-minute aggregates)
  - viral_spikes: 365 days (rare events, keep longer)
```

### PostgreSQL: Aggregated Scores

```sql
-- Aggregated sentiment scores (queryable by the opportunity scorer)
CREATE TABLE social_sentiment_scores (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    polarity FLOAT NOT NULL,
    volume_ratio FLOAT NOT NULL,
    credibility FLOAT NOT NULL,
    social_sentiment_score FLOAT NOT NULL,
    post_count INT NOT NULL,
    unique_authors INT NOT NULL,
    platform_breakdown JSONB NOT NULL DEFAULT '{}',
    viral_spike BOOLEAN NOT NULL DEFAULT FALSE,
    spike_ratio FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sentiment_symbol_time
    ON social_sentiment_scores (symbol, window_end DESC);

CREATE INDEX idx_sentiment_score
    ON social_sentiment_scores (social_sentiment_score);

-- Viral spike events for historical analysis
CREATE TABLE social_viral_spikes (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    spike_ratio FLOAT NOT NULL,
    mention_count INT NOT NULL,
    baseline_rate FLOAT NOT NULL,
    dominant_platform VARCHAR(20),
    sample_posts JSONB,               -- Top 5 posts by engagement
    detected_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,          -- When volume returned to normal
    price_impact_pct FLOAT,           -- Post-hoc price change correlation
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_viral_symbol_time
    ON social_viral_spikes (symbol, detected_at DESC);

-- Author credibility cache (updated daily)
CREATE TABLE social_author_credibility (
    author_id VARCHAR(100) PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    credibility_score FLOAT NOT NULL,
    is_known_bot BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Redis: Real-Time Cache

```
# Current sentiment score per symbol (TTL: 10 minutes)
social:sentiment:{symbol} -> JSON SentimentAggregate

# Volume baseline per symbol (TTL: 8 days, updated daily)
social:volume_baseline:{symbol} -> JSON { avg_5min_count: float }

# Known bot set (updated daily by bot detection job)
social:known_bots -> SET of author_ids

# SimHash index for duplicate detection (TTL: 1 hour)
social:simhash:{hash_prefix} -> SET of post_ids

# Viral spike cooldown per symbol (TTL: configured cooldown period)
social:viral_cooldown:{symbol} -> 1

# Rate limit counters per platform API
social:ratelimit:{platform} -> INT (TTL: 60s)
```

## Configuration

```yaml
social_sentiment:
  enabled: true

  # Data source configuration
  sources:
    twitter:
      enabled: true
      bearer_token: "${TWITTER_BEARER_TOKEN}"
      api_tier: "basic"                    # basic ($100/mo) or pro ($5000/mo)
      stream_rules_max: 25                 # Max filtered stream rules
      backfill_on_startup: true
      backfill_hours: 1
    reddit:
      enabled: true
      client_id: "${REDDIT_CLIENT_ID}"
      client_secret: "${REDDIT_CLIENT_SECRET}"
      user_agent: "TradeStream/1.0"
      poll_interval_seconds: 30
      subreddits:
        - cryptocurrency
        - bitcoin
        - ethtrader
        - CryptoMarkets
        - SatoshiStreetBets
    telegram:
      enabled: true
      api_id: "${TELEGRAM_API_ID}"
      api_hash: "${TELEGRAM_API_HASH}"
      channels:
        - WhaleCalls
        - CryptoSignalsIO
        - CoinGeckoAlerts
    discord:
      enabled: false                        # Phase 2
      bot_token: "${DISCORD_BOT_TOKEN}"
      servers: []

  # Aggregator fallback
  aggregator_fallback:
    enabled: true
    provider: "lunarcrush"
    api_key: "${LUNARCRUSH_API_KEY}"
    poll_interval_seconds: 300              # Every 5 minutes
    use_when: "primary_sources_degraded"    # or "always" for MVP

  # NLP model configuration
  model:
    primary: "finbert"
    model_path: "/models/finbert-onnx"
    batch_size: 32
    max_length: 128
    inference_device: "cpu"                 # or "cuda" for GPU
    fallback: "vader"                       # Simple fallback if model fails

  # Spam/bot filtering
  spam_filter:
    min_account_age_days: 30
    min_credibility_threshold: 0.3
    known_bot_refresh_hours: 24
    simhash_threshold: 3                   # Hamming distance for duplicate detection
    simhash_ttl_hours: 1

  # Aggregation
  aggregation:
    window_seconds: 300                     # 5-minute tumbling windows
    volume_baseline_days: 7                # Rolling average lookback
    min_posts_per_window: 3                # Minimum posts to compute score
    score_ttl_seconds: 600                 # Redis TTL for cached scores

  # Viral spike detection
  viral_detection:
    spike_threshold: 5.0                   # 5x baseline = spike
    min_mentions_per_window: 10
    sliding_window_seconds: 60
    slide_interval_seconds: 10
    cooldown_seconds: 300                  # 5 min between spike alerts
    trigger_re_aggregation: true

  # Integration with opportunity scoring
  scoring_integration:
    weight: 0.10                           # 10% of opportunity score
    default_score: 0.5                     # Neutral default when no data
    max_staleness_minutes: 15              # Ignore scores older than 15 min

  # Kafka topics
  kafka:
    raw_topics:
      - social.raw.twitter
      - social.raw.reddit
      - social.raw.telegram
      - social.raw.discord
    normalized_topic: social.normalized
    filtered_topic: social.filtered
    scored_topic: social.scored
    viral_alerts_topic: social.viral-alerts
    partitions: 20                         # One per tracked symbol
    replication_factor: 3
    retention_hours: 168                   # 7 days

  # Storage
  storage:
    influxdb:
      bucket: social_sentiment
      scored_posts_retention_days: 7
      aggregate_retention_days: 90
      viral_spike_retention_days: 365
    postgresql:
      table_prefix: social_
    redis:
      key_prefix: "social:"
      score_ttl_seconds: 600
      volume_baseline_ttl_seconds: 691200  # 8 days

  # Resource allocation
  resources:
    ingestion_replicas: 2
    scoring_replicas: 2                    # Parallelism for FinBERT inference
    aggregation_replicas: 1
    cpu_request: "500m"
    cpu_limit: "2000m"
    memory_request: "1Gi"
    memory_limit: "4Gi"                    # FinBERT model in memory
```

## Constraints

- Sentiment score must update at least every 5 minutes per symbol
- Viral spike detection must trigger within 60 seconds of a volume surge
- FinBERT inference latency must be < 5ms per post (batch mode, ONNX runtime)
- End-to-end pipeline latency (post ingestion to score update) must be < 60 seconds under normal load
- Must handle at least 10,000 posts per minute across all platforms
- Bot/spam filter must reject > 90% of known bot traffic
- Social sentiment weight must not exceed 15% of opportunity score (operator-configurable)
- System must degrade gracefully: if all social sources fail, opportunity scoring continues with the existing 5-factor formula (social_sentiment defaults to 0.5)
- All API credentials must be stored as Kubernetes secrets, never in config files
- Raw post text must not be stored longer than 7 days (privacy/compliance)
- Must respect all platform API rate limits without exceeding quotas

## Non-Goals

- **Trading execution**: This spec only produces a score; it does not trigger trades.
- **Individual post display**: The UI shows aggregate scores, not individual social media posts.
- **Influencer tracking**: Tracking specific influencer accounts is out of scope (see separate spec).
- **Sentiment on non-crypto assets**: Only cryptocurrency symbols are supported initially.
- **Custom NLP model training**: Phase 1 uses pre-trained FinBERT. Custom fine-tuning is Phase 2.
- **Paid social data resale**: Ingested data is for internal scoring only, not redistribution.
- **YouTube / TikTok / news scraping**: Video and news platforms are separate signal sources.
- **Backtesting social sentiment**: Historical correlation analysis is a follow-up effort.

## Acceptance Criteria

- [ ] Twitter/X filtered stream ingests posts for all tracked symbols in real-time
- [ ] Reddit polling ingests posts from configured subreddits every 30 seconds
- [ ] Telegram listener ingests messages from configured public channels
- [ ] All posts are normalized into the unified `SocialPost` schema
- [ ] Spam/bot filter assigns credibility scores and rejects posts below threshold
- [ ] FinBERT scores posts with polarity (-1 to +1) and confidence (0 to 1)
- [ ] Engagement weighting applies log-scaled weights based on likes/reposts
- [ ] 5-minute tumbling window produces `SentimentAggregate` per symbol
- [ ] Volume ratio is computed against 7-day rolling average from InfluxDB
- [ ] `social_sentiment_score` (0-1) is computed from polarity, volume, and credibility
- [ ] Score is written to Redis (TTL 10 min), PostgreSQL, and InfluxDB
- [ ] Opportunity scorer reads `social_sentiment_score` via MCP tool
- [ ] Opportunity scoring formula includes social sentiment at 10% weight
- [ ] Viral spike detection triggers within 60 seconds of a 5x volume surge
- [ ] Viral spikes trigger out-of-cycle re-aggregation
- [ ] Graceful degradation: scoring continues with 0.5 default if social pipeline fails
- [ ] LunarCrush fallback activates when primary sources are degraded
- [ ] All Kafka topics are created with correct partitioning and replication
- [ ] InfluxDB retention policies are applied per measurement
- [ ] Prometheus metrics are emitted for all pipeline stages
- [ ] End-to-end latency < 60 seconds under normal load
- [ ] Pipeline handles 10,000+ posts/minute without backpressure

## File Structure

```
services/social-sentiment/
├── ingestion/
│   ├── twitter_ingester.py
│   ├── reddit_ingester.py
│   ├── telegram_ingester.py
│   ├── discord_ingester.py
│   ├── lunarcrush_ingester.py          # Aggregator fallback
│   ├── normalizer.py                   # Unified post schema
│   └── BUILD
├── filtering/
│   ├── spam_bot_filter.py
│   ├── simhash_index.py
│   ├── known_bot_updater.py            # Daily bot list refresh
│   └── BUILD
├── scoring/
│   ├── finbert_scorer.py
│   ├── engagement_weighter.py
│   ├── model_loader.py                 # ONNX model management
│   └── BUILD
├── aggregation/
│   ├── sentiment_pipeline.py           # Beam pipeline definition
│   ├── sentiment_combine_fn.py
│   ├── volume_ratio.py
│   ├── viral_spike_detector.py
│   └── BUILD
├── storage/
│   ├── influxdb_writer.py
│   ├── postgres_writer.py
│   ├── redis_cache.py
│   └── BUILD
├── mcp/
│   ├── sentiment_mcp_server.py         # MCP tool for opportunity scorer
│   └── BUILD
├── config/
│   ├── social_sentiment_config.py
│   └── BUILD
├── protos/
│   └── social_sentiment.proto
├── tests/
│   ├── test_twitter_ingester.py
│   ├── test_reddit_ingester.py
│   ├── test_spam_filter.py
│   ├── test_finbert_scorer.py
│   ├── test_sentiment_pipeline.py
│   ├── test_viral_spike_detector.py
│   ├── test_volume_ratio.py
│   ├── test_social_sentiment_score.py
│   └── BUILD
├── Dockerfile
├── requirements.in
└── BUILD
```

## Metrics

### Pipeline Health

```python
# Ingestion
social_posts_ingested_total{platform, symbol}         # Posts received per platform
social_ingestion_errors_total{platform, error_type}    # Ingestion failures
social_ingestion_latency_ms{platform}                  # Time from post creation to Kafka
social_api_rate_limit_remaining{platform}               # Remaining API quota

# Filtering
social_posts_filtered_total{reason}                    # Posts rejected (bot, spam, duplicate)
social_credibility_histogram{platform}                 # Distribution of credibility scores
social_known_bots_count                                # Size of known bot set

# Scoring
social_finbert_inference_latency_ms                    # Per-batch inference time
social_finbert_batch_size                              # Posts per batch
social_polarity_histogram{symbol}                      # Distribution of polarity scores
social_model_errors_total{model, error_type}           # Model inference failures

# Aggregation
social_sentiment_score{symbol}                         # Current score per symbol (gauge)
social_aggregate_post_count{symbol}                    # Posts per 5-min window
social_aggregate_unique_authors{symbol}                # Unique authors per window
social_volume_ratio{symbol}                            # Current volume ratio
social_aggregation_latency_ms                          # Window computation time

# Viral Detection
social_viral_spikes_detected_total{symbol}             # Spike events
social_viral_spike_ratio{symbol}                       # Spike magnitude
social_viral_detection_latency_ms                      # Time from spike to detection

# Integration
social_sentiment_score_used_total{symbol}              # Times score was read by scorer
social_sentiment_fallback_total{reason}                # Fallback to default or aggregator
social_opportunity_score_with_sentiment_histogram       # Distribution of scores with social factor
social_opportunity_score_delta_histogram                # Difference vs without social factor

# Infrastructure
social_kafka_consumer_lag{topic, partition}             # Consumer lag per topic
social_redis_cache_hit_total{key_type}                 # Cache hits
social_redis_cache_miss_total{key_type}                # Cache misses
social_influxdb_write_latency_ms                       # InfluxDB write time
social_postgres_write_latency_ms                       # PostgreSQL write time
```

### Alerting Rules

```yaml
groups:
  - name: social-sentiment
    rules:
      - alert: SentimentPipelineStale
        expr: time() - social_sentiment_last_update_timestamp > 600
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Social sentiment not updated for {{ $labels.symbol }} in 10+ minutes"

      - alert: SentimentIngestionDown
        expr: rate(social_posts_ingested_total[5m]) == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "No social posts ingested from {{ $labels.platform }} in 10 minutes"

      - alert: FinBERTInferenceLatencyHigh
        expr: social_finbert_inference_latency_ms > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "FinBERT inference latency above 50ms (current: {{ $value }}ms)"

      - alert: SocialAPRateLimitLow
        expr: social_api_rate_limit_remaining < 100
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.platform }} API rate limit nearly exhausted"

      - alert: HighBotTrafficDetected
        expr: >
          rate(social_posts_filtered_total{reason="bot"}[5m])
          / rate(social_posts_ingested_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Over 50% of ingested posts are being filtered as bots"

      - alert: KafkaConsumerLagHigh
        expr: social_kafka_consumer_lag > 10000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Kafka consumer lag for {{ $labels.topic }} exceeds 10,000"

      - alert: ViralSpikeDetected
        expr: social_viral_spikes_detected_total > 0
        for: 0m
        labels:
          severity: info
        annotations:
          summary: "Viral spike detected for {{ $labels.symbol }} (ratio: {{ $value }})"
```

## Notes

### Phased Rollout

| Phase | Scope | Timeline |
|-------|-------|----------|
| **Phase 1 (MVP)** | LunarCrush aggregator integration, basic score, 10% weight | 2-3 weeks |
| **Phase 2** | Direct Twitter + Reddit ingestion, FinBERT scoring, spam filter | 4-6 weeks |
| **Phase 3** | Telegram + Discord, viral spike detection, custom model fine-tuning | 6-8 weeks |
| **Phase 4** | Historical backtesting, weight optimization, A/B testing vs baseline | 8-12 weeks |

### Cost Estimates

| Component | Monthly Cost |
|-----------|-------------|
| Twitter API (Basic tier) | $100 |
| Reddit API | Free |
| Telegram API | Free |
| LunarCrush (MVP fallback) | $200-500 |
| GPU inference (if needed) | $150-300 (spot instance) |
| Additional Kafka partitions | Included in existing cluster |
| InfluxDB storage (7-day raw) | ~$20 (estimated 50GB/month) |
| **Total (Phase 1 MVP)** | **$200-500/month** |
| **Total (Phase 2 full)** | **$300-900/month** |

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Twitter API pricing changes | LunarCrush fallback, Santiment as alternate provider |
| FinBERT misclassifies crypto slang | Phase 2 fine-tuning on labeled crypto dataset |
| Coordinated pump-and-dump campaigns | Credibility filter, volume cap, operator circuit breaker |
| API rate limit exhaustion | Per-platform rate limiter, adaptive polling intervals |
| Single viral post dominates score | Log-scale engagement weighting, 10x cap per post |
| Sentiment score lags price action | 60-second viral detection, sub-5-minute aggregation |
| Model serving failure | VADER fallback, LunarCrush fallback, default 0.5 score |

### Dependencies

- Existing opportunity scoring pipeline (spec: `opportunity-scoring/SPEC.md`)
- Kafka cluster (existing infrastructure)
- InfluxDB instance (existing infrastructure)
- Redis cluster (existing infrastructure)
- Apache Beam/Flink runner (existing infrastructure)
- Kubernetes cluster with capacity for 2-4 additional pods
