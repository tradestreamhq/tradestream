# Whale Wallet Monitoring

## Goal

Monitor on-chain whale wallet movements in real time and produce a `whale_activity_score` (0-1) that integrates into TradeStream's opportunity scoring formula, enabling the system to factor large-holder behavior into trading signal generation.

## Target Behavior

The Whale Monitoring pipeline continuously watches blockchain networks for large wallet movements, classifies each movement by type and likely intent, scores the impact, and publishes a normalized `whale_activity_score` that the Opportunity Scorer can consume alongside existing technical-analysis signals.

### End-to-End Flow

1. **Ingest** -- Subscribe to block-level data from multiple chains and third-party whale alert APIs.
2. **Detect** -- Identify transactions that exceed configurable whale thresholds.
3. **Classify** -- Label each movement (exchange inflow, exchange outflow, accumulation, distribution, OTC, DeFi).
4. **Score** -- Compute per-movement impact based on size, wallet history, movement type, and timing.
5. **Aggregate** -- Roll per-movement scores into a single `whale_activity_score` per token over a sliding window.
6. **Publish** -- Emit the score to Kafka for downstream consumption by the Opportunity Scorer.

### Architecture

```
+-------------------------------------------------------------------+
|                   WHALE MONITORING PIPELINE                        |
|                                                                    |
|  DATA SOURCES                                                      |
|  +-----------+  +-----------+  +------------+  +---------------+   |
|  | Blockchain|  | Block     |  | Whale Alert|  | On-Chain      |   |
|  | RPCs      |  | Explorers |  | API        |  | Analytics     |   |
|  | (Eth,Sol) |  | (Ethscan) |  |            |  | (Nansen,etc.) |   |
|  +-----+-----+  +-----+-----+  +------+-----+  +-------+-------+  |
|        |              |               |                |            |
|        v              v               v                v            |
|  +-----------------------------------------------------------+     |
|  |              MOVEMENT DETECTOR (Apache Beam)               |     |
|  |                                                            |     |
|  |  - Filter by whale thresholds per chain/token              |     |
|  |  - Deduplicate across sources                              |     |
|  |  - Enrich with wallet labels (exchange, known entity)      |     |
|  +----------------------------+-------------------------------+     |
|                               |                                     |
|                               v                                     |
|  +-----------------------------------------------------------+     |
|  |              MOVEMENT CLASSIFIER (Beam DoFn)               |     |
|  |                                                            |     |
|  |  - Exchange inflow / outflow detection                     |     |
|  |  - Accumulation / distribution pattern matching            |     |
|  |  - Whale-to-whale (OTC) identification                     |     |
|  |  - DeFi interaction classification                         |     |
|  +----------------------------+-------------------------------+     |
|                               |                                     |
|                               v                                     |
|  +-----------------------------------------------------------+     |
|  |              IMPACT SCORER (Beam DoFn)                     |     |
|  |                                                            |     |
|  |  - Size relative to 24h volume                             |     |
|  |  - Wallet historical accuracy (smart money weight)         |     |
|  |  - Movement type sentiment mapping                         |     |
|  |  - Timing pattern analysis                                 |     |
|  +----------------------------+-------------------------------+     |
|                               |                                     |
|                               v                                     |
|  +-----------------------------------------------------------+     |
|  |              AGGREGATOR (Beam windowed combine)            |     |
|  |                                                            |     |
|  |  - Sliding window: 1h window, 5m slide                     |     |
|  |  - Weighted average of scored movements                    |     |
|  |  - Normalize to whale_activity_score 0-1                   |     |
|  +----------------------------+-------------------------------+     |
|                               |                                     |
|                               v                                     |
|  +-----------------------------------------------------------+     |
|  |              KAFKA (topic: whale-activity)                 |     |
|  |                                                            |     |
|  |  Key: token symbol    Value: WhaleActivityEvent proto      |     |
|  +----------------------------+-------------------------------+     |
|                               |                                     |
|              +----------------+----------------+                    |
|              v                                 v                    |
|  +---------------------+         +--------------------------+      |
|  | Opportunity Scorer   |         | InfluxDB (time-series)   |      |
|  | (consumes score)     |         | PostgreSQL (wallet DB)   |      |
|  +---------------------+         +--------------------------+      |
+-------------------------------------------------------------------+
```

### Latency Targets

| Chain    | Block Time | Detection Target | End-to-End (to Kafka) |
|----------|-----------|------------------|-----------------------|
| Ethereum | ~12 s     | Within 1 block   | < 30 s                |
| Solana   | ~0.4 s    | Within 5 blocks  | < 10 s                |
| Bitcoin  | ~10 min   | Within 1 block   | < 60 s                |
| Polygon  | ~2 s      | Within 2 blocks  | < 15 s                |
| Arbitrum | ~0.25 s   | Within 10 blocks | < 15 s                |

## Data Sources

### Source Comparison

| Source | Type | Cost | Coverage | Latency | Rate Limits | Use Case |
|--------|------|------|----------|---------|-------------|----------|
| **Ethereum JSON-RPC** (Alchemy, Infura) | Blockchain RPC | Free tier: 300 req/s (Alchemy), 10 req/s (Infura). Growth: $49-199/mo | Ethereum, L2s | 1-2 blocks | Per plan | Primary Ethereum monitoring |
| **Solana RPC** (Helius, QuickNode) | Blockchain RPC | Free tier: 30 req/s (Helius). Pro: $49-99/mo | Solana | 1-5 slots | Per plan | Primary Solana monitoring |
| **Etherscan API** | Block explorer | Free: 5 calls/s. Pro: $199/mo, 20 calls/s | Ethereum, BSC, Polygon, Arb | 15-30 s behind tip | 5-20 calls/s | Wallet labeling, token transfers |
| **Whale Alert API** | Aggregator | Free: 10 req/min. Pro: $79/mo, 100 req/min. Enterprise: custom | BTC, ETH, XRP, ERC-20 | ~60 s | 10-100 req/min | Cross-chain whale alerts |
| **Nansen** | Analytics | Explorer: $150/mo. Pro: $1500/mo | Ethereum, Solana, L2s | Near-realtime | API access on Pro+ | Smart money labels, wallet profiling |
| **Arkham Intelligence** | Analytics | Free dashboard. API: Enterprise only | Multi-chain | Near-realtime | Enterprise | Entity identification |
| **Glassnode** | Analytics | Advanced: $29/mo. Professional: $799/mo | BTC, ETH | 1h granularity (free), 10m (pro) | Varies | On-chain metrics, exchange flows |
| **CoinGlass** | Derivatives | Free tier available. Pro: $30/mo | Cross-exchange | Real-time | Per plan | Exchange flow data |

### Recommended Initial Stack (Cost-Optimized)

| Role | Provider | Tier | Monthly Cost | Rationale |
|------|----------|------|-------------|-----------|
| Ethereum RPC | Alchemy | Growth | $49 | High rate limits, websocket support |
| Solana RPC | Helius | Developer | $49 | Best Solana RPC, DAS support |
| Explorer APIs | Etherscan + Solscan | Free | $0 | Wallet labels, token transfer history |
| Whale Alerts | Whale Alert API | Pro | $79 | Cross-chain whale notifications |
| Smart Money | Nansen | Explorer | $150 | Wallet labels and smart money tracking |
| Exchange Flows | Glassnode | Advanced | $29 | Exchange inflow/outflow metrics |
| **Total** | | | **$356/mo** | |

### Scaling Stack (Production)

| Role | Provider | Tier | Monthly Cost |
|------|----------|------|-------------|
| Multi-chain RPC | Alchemy | Scale | $199 |
| Solana RPC | Helius | Business | $99 |
| Explorer APIs | Etherscan | Pro | $199 |
| Whale Alerts | Whale Alert | Enterprise | ~$300 |
| Smart Money | Nansen | Pro | $1,500 |
| Exchange Flows | Glassnode | Professional | $799 |
| **Total** | | | **~$3,096/mo** |

## Whale Definition

### Configurable Thresholds

Whale thresholds are configurable per chain and per token, expressed either as absolute amounts or as a percentile of the holder distribution.

```proto
// protos/whale_monitoring.proto

syntax = "proto3";
package com.verlumen.tradestream.whale;

import "google/protobuf/timestamp.proto";

message WhaleThreshold {
  string chain = 1;              // "ethereum", "solana", "bitcoin"
  string token = 2;              // "ETH", "BTC", "SOL", "" for native
  oneof threshold_type {
    double absolute_amount = 3;  // e.g., 1000.0 for 1000 BTC
    double usd_value = 4;        // e.g., 1000000.0 for $1M
    int32 top_n_holders = 5;     // e.g., 100 for top 100 holders
  }
  double min_usd_value = 6;     // Floor: ignore movements below this USD value
}

message WhaleMovement {
  string movement_id = 1;
  string chain = 2;
  string tx_hash = 3;
  string from_address = 4;
  string to_address = 5;
  string token = 6;
  double amount = 7;
  double usd_value = 8;
  int64 block_number = 9;
  google.protobuf.Timestamp block_timestamp = 10;
  MovementType movement_type = 11;
  WalletLabel from_label = 12;
  WalletLabel to_label = 13;
  double impact_score = 14;        // 0.0 - 1.0
  SmartMoneyProfile smart_money = 15;
}

enum MovementType {
  MOVEMENT_TYPE_UNKNOWN = 0;
  EXCHANGE_INFLOW = 1;         // To exchange (potential sell pressure)
  EXCHANGE_OUTFLOW = 2;        // From exchange (accumulation, bullish)
  WHALE_TO_WHALE = 3;          // OTC or internal transfer (neutral)
  TOKEN_ACCUMULATION = 4;      // New position building (bullish)
  TOKEN_DISTRIBUTION = 5;      // Selling / spreading across wallets (bearish)
  DEFI_INTERACTION = 6;        // LP, staking, yield farming
  BRIDGE_TRANSFER = 7;         // Cross-chain bridge movement
}

message WalletLabel {
  string address = 1;
  string entity_name = 2;       // "Binance", "a]6z", "Unknown"
  WalletType wallet_type = 3;
  bool is_smart_money = 4;
  double historical_accuracy = 5;  // 0.0 - 1.0, how often this wallet is "right"
}

enum WalletType {
  WALLET_TYPE_UNKNOWN = 0;
  EXCHANGE = 1;
  INSTITUTIONAL = 2;
  WHALE_INDIVIDUAL = 3;
  DEFI_PROTOCOL = 4;
  BRIDGE = 5;
  TREASURY = 6;
}

message SmartMoneyProfile {
  double win_rate = 1;          // % of trades that were profitable
  double avg_return = 2;        // Average return per trade
  int32 total_trades = 3;       // Number of tracked trades
  int32 lookback_days = 4;      // Analysis window
  double confidence = 5;        // Confidence in the profile (0-1)
}

message WhaleActivityEvent {
  string token = 1;
  double whale_activity_score = 2;   // 0.0 - 1.0
  double bullish_pressure = 3;       // 0.0 - 1.0
  double bearish_pressure = 4;       // 0.0 - 1.0
  int32 movements_in_window = 5;
  double total_usd_volume = 6;
  google.protobuf.Timestamp window_start = 7;
  google.protobuf.Timestamp window_end = 8;
  repeated WhaleMovement top_movements = 9;  // Top 5 by impact
  google.protobuf.Timestamp timestamp = 10;
}
```

### Default Thresholds

| Chain/Token | Absolute Threshold | USD Floor | Rationale |
|------------|-------------------|-----------|-----------|
| BTC | 100 BTC | $1,000,000 | ~0.0005% of supply, significant market impact |
| ETH | 1,000 ETH | $500,000 | ~0.001% of supply |
| SOL | 10,000 SOL | $200,000 | Accounts for higher token count |
| USDT/USDC | N/A | $5,000,000 | Stablecoin moves only matter at large scale |
| ERC-20 (generic) | Top 100 holders | $100,000 | Percentile-based for long-tail tokens |

## Movement Types

### Classification Logic

```java
// src/main/java/com/verlumen/tradestream/whale/MovementClassifier.java

public final class MovementClassifier {

    private final ExchangeAddressRegistry exchangeRegistry;
    private final DeFiProtocolRegistry defiRegistry;
    private final BridgeAddressRegistry bridgeRegistry;

    /**
     * Classify a raw whale movement based on source/destination wallet labels.
     *
     * Classification priority:
     * 1. Bridge transfers (cross-chain, neutral)
     * 2. Exchange inflow/outflow (sell/buy pressure)
     * 3. DeFi interactions (yield, LP)
     * 4. Whale-to-whale (OTC, neutral)
     * 5. Accumulation/distribution (pattern-based)
     */
    public MovementType classify(WhaleMovement movement) {
        boolean fromExchange = exchangeRegistry.isExchange(movement.getFromAddress());
        boolean toExchange = exchangeRegistry.isExchange(movement.getToAddress());
        boolean toDeFi = defiRegistry.isProtocol(movement.getToAddress());
        boolean fromDeFi = defiRegistry.isProtocol(movement.getFromAddress());
        boolean toBridge = bridgeRegistry.isBridge(movement.getToAddress());
        boolean fromBridge = bridgeRegistry.isBridge(movement.getFromAddress());

        // Bridge transfers
        if (toBridge || fromBridge) {
            return MovementType.BRIDGE_TRANSFER;
        }

        // Exchange flows
        if (!fromExchange && toExchange) {
            return MovementType.EXCHANGE_INFLOW;  // Depositing to sell
        }
        if (fromExchange && !toExchange) {
            return MovementType.EXCHANGE_OUTFLOW;  // Withdrawing to hold
        }

        // DeFi interactions
        if (toDeFi || fromDeFi) {
            return MovementType.DEFI_INTERACTION;
        }

        // Whale-to-whale (both addresses are known whales, neither is exchange)
        if (isKnownWhale(movement.getFromAddress())
                && isKnownWhale(movement.getToAddress())) {
            return MovementType.WHALE_TO_WHALE;
        }

        // Pattern-based: accumulation vs distribution
        return classifyByPattern(movement);
    }

    /**
     * Detect accumulation or distribution based on recent wallet activity.
     *
     * Accumulation: wallet has received multiple inflows of this token recently.
     * Distribution: wallet has sent multiple outflows of this token recently.
     */
    private MovementType classifyByPattern(WhaleMovement movement) {
        WalletHistory history = getRecentHistory(
            movement.getToAddress(), movement.getToken(), Duration.ofHours(24));

        if (history.getInflows() > history.getOutflows() * 2) {
            return MovementType.TOKEN_ACCUMULATION;
        }

        WalletHistory senderHistory = getRecentHistory(
            movement.getFromAddress(), movement.getToken(), Duration.ofHours(24));

        if (senderHistory.getOutflows() > senderHistory.getInflows() * 2) {
            return MovementType.TOKEN_DISTRIBUTION;
        }

        return MovementType.MOVEMENT_TYPE_UNKNOWN;
    }
}
```

### Movement Type Sentiment Mapping

| Movement Type | Sentiment | Score Modifier | Reasoning |
|--------------|-----------|---------------|-----------|
| Exchange Inflow | Bearish | -0.3 to -0.8 | Depositing to exchange likely to sell |
| Exchange Outflow | Bullish | +0.3 to +0.8 | Withdrawing to hold, reducing sell pressure |
| Whale-to-Whale | Neutral | -0.1 to +0.1 | OTC trade, minimal market impact |
| Token Accumulation | Bullish | +0.2 to +0.6 | Building new position |
| Token Distribution | Bearish | -0.2 to -0.6 | Distributing holdings |
| DeFi Interaction | Slightly Bullish | +0.1 to +0.3 | Productive use of capital, long-term conviction |
| Bridge Transfer | Neutral | -0.05 to +0.05 | Cross-chain movement, intent unclear |

## Impact Scoring

Each whale movement receives an impact score (0.0 - 1.0) that reflects how significant the movement is for market sentiment.

### Scoring Formula

```java
// src/main/java/com/verlumen/tradestream/whale/ImpactScorer.java

public final class ImpactScorer {

    private final WhaleMonitoringConfig config;
    private final SmartMoneyTracker smartMoneyTracker;

    /**
     * Score the impact of a single whale movement.
     *
     * Components:
     *   1. Size factor (40%): Movement size relative to 24h trading volume
     *   2. Wallet factor (25%): Historical accuracy of this wallet
     *   3. Type factor (20%): Sentiment weight from movement classification
     *   4. Timing factor (15%): Unusual timing (off-hours, clustered activity)
     *
     * Returns signed score: negative = bearish, positive = bullish.
     * Magnitude indicates strength (0.0 = no impact, 1.0 = maximum).
     */
    public double score(WhaleMovement movement, MarketContext context) {
        double sizeFactor = computeSizeFactor(movement, context);
        double walletFactor = computeWalletFactor(movement);
        double typeFactor = computeTypeFactor(movement.getMovementType());
        double timingFactor = computeTimingFactor(movement, context);

        double rawScore =
            config.getWeights().getSize() * sizeFactor
            + config.getWeights().getWallet() * walletFactor
            + config.getWeights().getType() * typeFactor
            + config.getWeights().getTiming() * timingFactor;

        // Clamp to [-1.0, 1.0]
        return Math.max(-1.0, Math.min(1.0, rawScore));
    }

    /**
     * Size relative to 24h volume.
     * $10M move on a $100M daily volume token = 0.1 = moderate.
     * $10M move on a $10M daily volume token = 1.0 = massive.
     */
    private double computeSizeFactor(WhaleMovement movement, MarketContext context) {
        if (context.getDailyVolumeUsd() <= 0) {
            return 0.5; // Default when volume unknown
        }
        double ratio = movement.getUsdValue() / context.getDailyVolumeUsd();
        // Log scale to handle wide range: 0.01% of volume to 100% of volume
        // log10(1) = 0, log10(10) = 1, log10(100) = 2
        double logRatio = Math.log10(Math.max(ratio * 100, 1.0)) / 2.0;
        return Math.min(1.0, logRatio);
    }

    /**
     * Weight by wallet's historical accuracy.
     * Smart money wallets (high win rate) get higher impact.
     * Unknown wallets get a neutral baseline.
     */
    private double computeWalletFactor(WhaleMovement movement) {
        SmartMoneyProfile profile = movement.getSmartMoney();
        if (profile == null || profile.getTotalTrades() < 10) {
            return 0.5; // Insufficient history, neutral weight
        }

        // Scale from 0.3 (bad track record) to 1.0 (excellent track record)
        // Win rate of 50% = 0.5 factor, 70% = 0.7 factor, etc.
        double winRateScore = profile.getWinRate();

        // Boost confidence for wallets with more data points
        double dataConfidence = Math.min(1.0, profile.getTotalTrades() / 100.0);

        return 0.3 + 0.7 * winRateScore * dataConfidence;
    }

    /**
     * Base sentiment from movement type.
     * Returns signed value: negative for bearish, positive for bullish.
     */
    private double computeTypeFactor(MovementType type) {
        switch (type) {
            case EXCHANGE_INFLOW:     return -0.6;
            case EXCHANGE_OUTFLOW:    return +0.6;
            case TOKEN_ACCUMULATION:  return +0.4;
            case TOKEN_DISTRIBUTION:  return -0.4;
            case DEFI_INTERACTION:    return +0.2;
            case WHALE_TO_WHALE:      return  0.0;
            case BRIDGE_TRANSFER:     return  0.0;
            default:                  return  0.0;
        }
    }

    /**
     * Unusual timing amplifies impact.
     *
     * - Off-hours movements (weekends, late night UTC) are more deliberate.
     * - Clustered movements (many whales moving at once) amplify signal.
     */
    private double computeTimingFactor(WhaleMovement movement, MarketContext context) {
        double timingScore = 0.5; // Baseline

        // Off-hours bonus: movements during low-activity periods are more intentional
        int hourUtc = movement.getBlockTimestamp()
            .toInstant().atZone(ZoneOffset.UTC).getHour();
        boolean isOffHours = hourUtc < 6 || hourUtc > 22; // UTC off-hours
        if (isOffHours) {
            timingScore += 0.2;
        }

        // Cluster detection: multiple whale moves in same token within 30 min
        int recentMoves = context.getWhaleMovementsInLast30Min();
        if (recentMoves >= 5) {
            timingScore += 0.3; // Strong cluster
        } else if (recentMoves >= 3) {
            timingScore += 0.15; // Moderate cluster
        }

        return Math.min(1.0, timingScore);
    }
}
```

### Impact Score Weights (configurable)

| Component | Weight | Range | Description |
|-----------|--------|-------|-------------|
| Size Factor | 40% | 0.0 - 1.0 | Movement size relative to daily volume |
| Wallet Factor | 25% | 0.3 - 1.0 | Historical wallet accuracy |
| Type Factor | 20% | -0.6 - +0.6 | Sentiment from movement classification |
| Timing Factor | 15% | 0.0 - 1.0 | Unusual timing amplification |

## Smart Money Tracking

### Smart Money Identification

Wallets are scored as "smart money" based on historical profitability of their on-chain movements.

```java
// src/main/java/com/verlumen/tradestream/whale/SmartMoneyTracker.java

public final class SmartMoneyTracker {

    private static final int MIN_TRADES_FOR_PROFILE = 10;
    private static final int LOOKBACK_DAYS = 90;
    private static final double SMART_MONEY_THRESHOLD = 0.60; // 60% win rate

    /**
     * Build a profitability profile for a wallet by analyzing its historical
     * on-chain movements against subsequent price action.
     *
     * For each past movement:
     *   1. Record movement timestamp, token, type (buy/accumulate vs sell/distribute)
     *   2. Check price 24h and 7d after the movement
     *   3. Mark as "correct" if:
     *      - Buy/accumulate and price rose > 2%
     *      - Sell/distribute and price fell > 2%
     *   4. Compute win rate over all tracked movements
     */
    public SmartMoneyProfile buildProfile(String address) {
        List<HistoricalMovement> history = walletHistoryStore.getMovements(
            address, Instant.now().minus(Duration.ofDays(LOOKBACK_DAYS)));

        if (history.size() < MIN_TRADES_FOR_PROFILE) {
            return SmartMoneyProfile.newBuilder()
                .setTotalTrades(history.size())
                .setConfidence(0.0)
                .build();
        }

        int wins = 0;
        double totalReturn = 0.0;

        for (HistoricalMovement move : history) {
            PriceChange priceAfter = priceService.getPriceChange(
                move.getToken(), move.getTimestamp(), Duration.ofDays(7));

            boolean isBullishMove = move.getType() == MovementType.EXCHANGE_OUTFLOW
                || move.getType() == MovementType.TOKEN_ACCUMULATION;
            boolean isBearishMove = move.getType() == MovementType.EXCHANGE_INFLOW
                || move.getType() == MovementType.TOKEN_DISTRIBUTION;

            double returnPct = priceAfter.getPercentChange();

            if (isBullishMove && returnPct > 0.02) {
                wins++;
                totalReturn += returnPct;
            } else if (isBearishMove && returnPct < -0.02) {
                wins++;
                totalReturn += Math.abs(returnPct);
            }
        }

        double winRate = (double) wins / history.size();
        double avgReturn = totalReturn / history.size();

        // Confidence scales with data volume
        double confidence = Math.min(1.0, history.size() / 50.0);

        return SmartMoneyProfile.newBuilder()
            .setWinRate(winRate)
            .setAvgReturn(avgReturn)
            .setTotalTrades(history.size())
            .setLookbackDays(LOOKBACK_DAYS)
            .setConfidence(confidence)
            .build();
    }

    /**
     * Determine if a wallet qualifies as smart money.
     */
    public boolean isSmartMoney(String address) {
        SmartMoneyProfile profile = buildProfile(address);
        return profile.getConfidence() > 0.5
            && profile.getWinRate() >= SMART_MONEY_THRESHOLD
            && profile.getTotalTrades() >= MIN_TRADES_FOR_PROFILE;
    }
}
```

### Smart Money Weight Amplification

Smart money movements receive an amplified weight in the aggregated score:

| Wallet Category | Weight Multiplier | Rationale |
|----------------|-------------------|-----------|
| Smart money (>70% win rate) | 2.0x | Historically very accurate |
| Smart money (60-70% win rate) | 1.5x | Above-average accuracy |
| Unknown / insufficient data | 1.0x | Neutral baseline |
| Known poor performer (<40% win rate) | 0.5x | Historically inaccurate |

### Profile Refresh Schedule

Smart money profiles are computationally expensive. Refresh on a cadence, not per-movement.

| Wallet Category | Refresh Interval | Storage |
|----------------|------------------|---------|
| Top 500 tracked wallets | Every 6 hours | PostgreSQL |
| Active whales (moved in last 7d) | Every 24 hours | PostgreSQL |
| Historical / inactive wallets | Every 7 days | PostgreSQL |

## Integration with Opportunity Scoring

### Updated Scoring Formula

The existing opportunity scoring formula is extended with a `whale_activity` factor. The total weights are redistributed to sum to 1.0:

| Factor | Original Weight | New Weight | Change |
|--------|----------------|------------|--------|
| Confidence | 25% | 22% | -3% |
| Expected Return | 30% | 27% | -3% |
| Strategy Consensus | 20% | 18% | -2% |
| Volatility | 15% | 13% | -2% |
| Freshness | 10% | 10% | 0% |
| **Whale Activity** | -- | **10%** | **+10%** |

### whale_activity_score Computation

The `whale_activity_score` is a normalized value between 0.0 and 1.0 that represents net whale sentiment over a sliding window.

```python
def compute_whale_activity_score(
    movements: list[ScoredMovement],
    window_minutes: int = 60,
    smart_money_multiplier: dict = None
) -> float:
    """
    Aggregate scored whale movements into a single whale_activity_score.

    A score of 0.5 is neutral (balanced or no whale activity).
    Scores > 0.5 indicate net bullish whale behavior.
    Scores < 0.5 indicate net bearish whale behavior.

    Args:
        movements: Scored whale movements within the window.
        window_minutes: Sliding window size.
        smart_money_multiplier: Weight multipliers by wallet category.

    Returns:
        Float between 0.0 and 1.0.
    """
    if not movements:
        return 0.5  # No data = neutral

    multipliers = smart_money_multiplier or {
        "smart_high": 2.0,
        "smart_medium": 1.5,
        "unknown": 1.0,
        "poor": 0.5,
    }

    weighted_sum = 0.0
    total_weight = 0.0

    for m in movements:
        # Determine smart money category
        category = classify_wallet_category(m.wallet_profile)
        multiplier = multipliers.get(category, 1.0)

        # Weight by USD volume (larger moves matter more)
        volume_weight = math.log10(max(m.usd_value, 1000)) / 10.0  # Normalize

        weight = multiplier * volume_weight
        weighted_sum += m.impact_score * weight  # impact_score is signed [-1, 1]
        total_weight += weight

    if total_weight == 0:
        return 0.5

    # Raw score in [-1, 1] range
    raw_score = weighted_sum / total_weight

    # Normalize to [0, 1]: -1 -> 0.0, 0 -> 0.5, +1 -> 1.0
    normalized = (raw_score + 1.0) / 2.0

    return round(max(0.0, min(1.0, normalized)), 4)
```

### Opportunity Score Integration

```python
def calculate_opportunity_score_v2(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    whale_activity_score: float = 0.5,  # Default neutral
    market_regime: str = "normal"
) -> float:
    """
    Extended opportunity score incorporating whale activity.
    """
    caps = get_regime_adjusted_caps(market_regime)

    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = min(risk_adjusted_return / caps.max_return, 1.0)
    volatility_score = min(volatility / caps.max_volatility, 1.0)
    freshness_score = max(0, 1 - (minutes_ago / 60))

    opportunity_score = (
        0.22 * confidence
        + 0.27 * return_score
        + 0.18 * consensus_pct
        + 0.13 * volatility_score
        + 0.10 * freshness_score
        + 0.10 * whale_activity_score  # New factor
    ) * 100

    return round(opportunity_score, 1)
```

### Signal Suppression / Boost Rules

In addition to the weighted score contribution, whale activity applies hard rules:

| Condition | Effect | Rationale |
|-----------|--------|-----------|
| Exchange inflow > 5% of daily volume | Suppress BUY score by 15% | Major sell pressure imminent |
| Exchange outflow > 5% of daily volume | Boost BUY score by 10% | Major accumulation signal |
| Smart money cluster (3+ wallets, same direction, 30 min) | Boost/suppress by 20% | High-conviction directional signal |
| Whale distribution + exchange inflow together | Suppress BUY score by 25% | Double bearish signal |

```python
def apply_whale_adjustments(
    opportunity_score: float,
    whale_events: list[WhaleActivityEvent],
    daily_volume_usd: float
) -> float:
    """
    Apply hard whale-based adjustments to the opportunity score.
    These are applied AFTER the weighted formula for extreme scenarios.
    """
    adjusted = opportunity_score

    for event in whale_events:
        # Check for massive exchange inflows
        inflow_pct = event.exchange_inflow_usd / daily_volume_usd
        if inflow_pct > 0.05:
            adjusted *= 0.85  # 15% suppression

        # Check for massive exchange outflows
        outflow_pct = event.exchange_outflow_usd / daily_volume_usd
        if outflow_pct > 0.05:
            adjusted *= 1.10  # 10% boost

        # Smart money cluster detection
        if event.smart_money_cluster_detected:
            if event.cluster_direction == "bullish":
                adjusted *= 1.20
            elif event.cluster_direction == "bearish":
                adjusted *= 0.80

    return round(max(0, min(100, adjusted)), 1)
```

## Implementation

### Apache Beam Pipeline

```java
// src/main/java/com/verlumen/tradestream/whale/WhaleMonitoringPipeline.java

public final class WhaleMonitoringPipeline {

    public static Pipeline create(WhaleMonitoringConfig config) {
        PipelineOptions options = PipelineOptionsFactory.create();
        Pipeline pipeline = Pipeline.create(options);

        // 1. Read from multiple sources in parallel
        PCollection<RawTransaction> ethereumTxns = pipeline
            .apply("ReadEthereumBlocks",
                new EthereumBlockReader(config.getEthereumRpcUrl()))
            .apply("FilterWhaleThreshold",
                ParDo.of(new WhaleThresholdFilter(
                    config.getThresholds("ethereum"))));

        PCollection<RawTransaction> solanaTxns = pipeline
            .apply("ReadSolanaBlocks",
                new SolanaBlockReader(config.getSolanaRpcUrl()))
            .apply("FilterWhaleThreshold",
                ParDo.of(new WhaleThresholdFilter(
                    config.getThresholds("solana"))));

        PCollection<RawTransaction> whaleAlerts = pipeline
            .apply("ReadWhaleAlertAPI",
                new WhaleAlertReader(config.getWhaleAlertApiKey()))
            .apply("FilterWhaleThreshold",
                ParDo.of(new WhaleThresholdFilter(
                    config.getDefaultThresholds())));

        // 2. Flatten all sources and deduplicate
        PCollection<RawTransaction> allTxns = PCollectionList
            .of(ethereumTxns).and(solanaTxns).and(whaleAlerts)
            .apply("FlattenSources", Flatten.pCollections())
            .apply("DeduplicateByTxHash",
                Deduplicate.<RawTransaction>withKeys(
                    RawTransaction::getTxHash)
                .withDuration(Duration.standardMinutes(10)));

        // 3. Enrich with wallet labels
        PCollection<WhaleMovement> enrichedMovements = allTxns
            .apply("EnrichWalletLabels",
                ParDo.of(new WalletLabelEnricher(config)));

        // 4. Classify movement type
        PCollection<WhaleMovement> classifiedMovements = enrichedMovements
            .apply("ClassifyMovement",
                ParDo.of(new MovementClassifierDoFn()));

        // 5. Score impact
        PCollection<WhaleMovement> scoredMovements = classifiedMovements
            .apply("ScoreImpact",
                ParDo.of(new ImpactScorerDoFn(config)));

        // 6. Persist individual movements
        scoredMovements
            .apply("WriteToInfluxDB",
                new InfluxDBWriter(config.getInfluxDbConfig()));

        scoredMovements
            .apply("WriteToPostgres",
                new PostgresMovementWriter(config.getPostgresConfig()));

        // 7. Window and aggregate into whale_activity_score
        PCollection<WhaleActivityEvent> activityEvents = scoredMovements
            .apply("WindowInto1hSliding5m",
                Window.<WhaleMovement>into(
                    SlidingWindows.of(Duration.standardHours(1))
                        .every(Duration.standardMinutes(5)))
                .withAllowedLateness(Duration.standardMinutes(2))
                .accumulatingFiredPanes())
            .apply("KeyByToken",
                WithKeys.of(WhaleMovement::getToken))
            .apply("AggregateByToken",
                Combine.perKey(new WhaleActivityAggregator()))
            .apply("ToActivityEvent",
                ParDo.of(new ActivityEventFormatter()));

        // 8. Publish to Kafka
        activityEvents
            .apply("SerializeProto",
                MapElements.into(TypeDescriptors.kvs(
                    TypeDescriptors.strings(),
                    TypeDescriptor.of(byte[].class)))
                .via(event -> KV.of(
                    event.getToken(),
                    event.toByteArray())))
            .apply("WriteToKafka",
                KafkaIO.<String, byte[]>write()
                    .withBootstrapServers(config.getKafkaBootstrap())
                    .withTopic("whale-activity")
                    .withKeySerializer(StringSerializer.class)
                    .withValueSerializer(ByteArraySerializer.class));

        // 9. Cache latest score in Redis for fast lookup
        activityEvents
            .apply("CacheInRedis",
                ParDo.of(new RedisCacheWriter(config.getRedisUrl())));

        return pipeline;
    }
}
```

### Aggregator Implementation

```java
// src/main/java/com/verlumen/tradestream/whale/WhaleActivityAggregator.java

public final class WhaleActivityAggregator
    extends Combine.CombineFn<WhaleMovement, WhaleActivityAccumulator, WhaleActivityEvent> {

    @Override
    public WhaleActivityAccumulator createAccumulator() {
        return new WhaleActivityAccumulator();
    }

    @Override
    public WhaleActivityAccumulator addInput(
            WhaleActivityAccumulator acc, WhaleMovement movement) {
        acc.addMovement(movement);
        return acc;
    }

    @Override
    public WhaleActivityAccumulator mergeAccumulators(
            Iterable<WhaleActivityAccumulator> accumulators) {
        WhaleActivityAccumulator merged = new WhaleActivityAccumulator();
        for (WhaleActivityAccumulator acc : accumulators) {
            merged.merge(acc);
        }
        return merged;
    }

    @Override
    public WhaleActivityEvent extractOutput(WhaleActivityAccumulator acc) {
        double bullishPressure = acc.getBullishVolume() /
            Math.max(acc.getTotalVolume(), 1.0);
        double bearishPressure = acc.getBearishVolume() /
            Math.max(acc.getTotalVolume(), 1.0);

        // Weighted average of signed impact scores
        double whaleActivityScore = acc.getWeightedImpactSum() /
            Math.max(acc.getTotalWeight(), 1.0);

        // Normalize from [-1, 1] to [0, 1]
        double normalizedScore = (whaleActivityScore + 1.0) / 2.0;

        return WhaleActivityEvent.newBuilder()
            .setToken(acc.getToken())
            .setWhaleActivityScore(normalizedScore)
            .setBullishPressure(bullishPressure)
            .setBearishPressure(bearishPressure)
            .setMovementsInWindow(acc.getMovementCount())
            .setTotalUsdVolume(acc.getTotalVolume())
            .addAllTopMovements(acc.getTopMovementsByImpact(5))
            .setTimestamp(Timestamps.now())
            .build();
    }
}
```

### Wallet Label Enrichment

```java
// src/main/java/com/verlumen/tradestream/whale/WalletLabelEnricher.java

public final class WalletLabelEnricher extends DoFn<RawTransaction, WhaleMovement> {

    private final ExchangeAddressRegistry exchangeRegistry;
    private final RedisClient redisClient;
    private final SmartMoneyTracker smartMoneyTracker;

    /**
     * Enrich a raw transaction with wallet labels from multiple sources:
     * 1. Local exchange address registry (in-memory, fast)
     * 2. Redis cache of previously resolved labels
     * 3. Etherscan/Nansen API call (slow, cached)
     */
    @ProcessElement
    public void processElement(ProcessContext ctx) {
        RawTransaction tx = ctx.element();

        WalletLabel fromLabel = resolveLabel(tx.getFromAddress(), tx.getChain());
        WalletLabel toLabel = resolveLabel(tx.getToAddress(), tx.getChain());

        SmartMoneyProfile smartMoney = smartMoneyTracker.getProfile(tx.getFromAddress());

        WhaleMovement movement = WhaleMovement.newBuilder()
            .setMovementId(generateMovementId(tx))
            .setChain(tx.getChain())
            .setTxHash(tx.getTxHash())
            .setFromAddress(tx.getFromAddress())
            .setToAddress(tx.getToAddress())
            .setToken(tx.getToken())
            .setAmount(tx.getAmount())
            .setUsdValue(tx.getUsdValue())
            .setBlockNumber(tx.getBlockNumber())
            .setBlockTimestamp(tx.getBlockTimestamp())
            .setFromLabel(fromLabel)
            .setToLabel(toLabel)
            .setSmartMoney(smartMoney)
            .build();

        ctx.output(movement);
    }

    private WalletLabel resolveLabel(String address, String chain) {
        // 1. Check local registry (fastest)
        Optional<WalletLabel> local = exchangeRegistry.lookup(address);
        if (local.isPresent()) {
            return local.get();
        }

        // 2. Check Redis cache
        String cacheKey = "wallet:label:" + chain + ":" + address;
        Optional<WalletLabel> cached = redisClient.get(cacheKey, WalletLabel.class);
        if (cached.isPresent()) {
            return cached.get();
        }

        // 3. Query external API (Etherscan/Nansen) - async with fallback
        try {
            WalletLabel resolved = externalLabelService.resolve(address, chain);
            redisClient.setEx(cacheKey, resolved, Duration.ofDays(7));
            return resolved;
        } catch (Exception e) {
            return WalletLabel.newBuilder()
                .setAddress(address)
                .setEntityName("Unknown")
                .setWalletType(WalletType.WALLET_TYPE_UNKNOWN)
                .build();
        }
    }
}
```

### Exchange Address Registry

```java
// src/main/java/com/verlumen/tradestream/whale/ExchangeAddressRegistry.java

/**
 * In-memory registry of known exchange addresses.
 * Loaded from PostgreSQL at startup, refreshed every 6 hours.
 */
public final class ExchangeAddressRegistry {

    private volatile ImmutableMap<String, String> exchangeAddresses;

    @Inject
    public ExchangeAddressRegistry(DataSource dataSource) {
        this.exchangeAddresses = loadFromDatabase(dataSource);
    }

    public boolean isExchange(String address) {
        return exchangeAddresses.containsKey(address.toLowerCase());
    }

    public Optional<WalletLabel> lookup(String address) {
        String entity = exchangeAddresses.get(address.toLowerCase());
        if (entity == null) {
            return Optional.empty();
        }
        return Optional.of(WalletLabel.newBuilder()
            .setAddress(address)
            .setEntityName(entity)
            .setWalletType(WalletType.EXCHANGE)
            .build());
    }

    /**
     * Refresh registry from database.
     * Called by a scheduled executor every 6 hours.
     */
    public void refresh(DataSource dataSource) {
        this.exchangeAddresses = loadFromDatabase(dataSource);
    }

    private ImmutableMap<String, String> loadFromDatabase(DataSource dataSource) {
        // Query: SELECT address, entity_name FROM exchange_addresses WHERE active = true
        // Returns ~50,000 known exchange addresses across all chains
        // ...
    }
}
```

## Configuration

```yaml
whale_monitoring:
  # Chain-specific RPC configuration
  chains:
    ethereum:
      rpc_url: "${ETHEREUM_RPC_URL}"
      websocket_url: "${ETHEREUM_WS_URL}"
      poll_interval_ms: 12000       # ~1 block
      batch_size: 10                # Blocks per batch
      confirmations: 1              # Blocks before processing
    solana:
      rpc_url: "${SOLANA_RPC_URL}"
      websocket_url: "${SOLANA_WS_URL}"
      poll_interval_ms: 2000        # ~5 slots
      batch_size: 50
      confirmations: 5
    bitcoin:
      rpc_url: "${BITCOIN_RPC_URL}"
      poll_interval_ms: 60000       # ~1 block
      batch_size: 1
      confirmations: 1

  # External API keys
  apis:
    whale_alert:
      api_key: "${WHALE_ALERT_API_KEY}"
      poll_interval_seconds: 30
      min_usd_value: 500000
    etherscan:
      api_key: "${ETHERSCAN_API_KEY}"
      rate_limit_per_second: 5
    nansen:
      api_key: "${NANSEN_API_KEY}"
      enabled: true
    glassnode:
      api_key: "${GLASSNODE_API_KEY}"
      enabled: true

  # Whale thresholds
  thresholds:
    defaults:
      min_usd_value: 100000
    per_token:
      BTC:
        absolute_amount: 100
        min_usd_value: 1000000
      ETH:
        absolute_amount: 1000
        min_usd_value: 500000
      SOL:
        absolute_amount: 10000
        min_usd_value: 200000
      USDT:
        min_usd_value: 5000000
      USDC:
        min_usd_value: 5000000

  # Impact scoring weights
  scoring:
    weights:
      size: 0.40
      wallet: 0.25
      type: 0.20
      timing: 0.15
    smart_money:
      min_trades: 10
      lookback_days: 90
      threshold_win_rate: 0.60
      multipliers:
        smart_high: 2.0     # >70% win rate
        smart_medium: 1.5   # 60-70% win rate
        unknown: 1.0
        poor: 0.5           # <40% win rate

  # Aggregation windows
  aggregation:
    window_duration_minutes: 60
    slide_interval_minutes: 5
    allowed_lateness_minutes: 2

  # Signal suppression thresholds
  suppression:
    exchange_inflow_volume_pct: 0.05    # 5% of daily volume
    exchange_outflow_volume_pct: 0.05
    smart_money_cluster_count: 3
    smart_money_cluster_window_min: 30
    buy_suppression_factor: 0.85
    buy_boost_factor: 1.10
    cluster_boost_factor: 1.20
    cluster_suppress_factor: 0.80
    double_bearish_suppress_factor: 0.75

  # Integration with opportunity scoring
  opportunity_scoring_integration:
    enabled: true
    weight: 0.10                       # 10% of total opportunity score
    fallback_score: 0.5                # Neutral if no whale data available
    stale_data_threshold_minutes: 30   # Use fallback if data older than this

  # Storage
  storage:
    influxdb:
      url: "${INFLUXDB_URL}"
      bucket: "whale_movements"
      retention_days: 90
    postgres:
      url: "${POSTGRES_URL}"
      tables:
        movements: "whale_movements"
        wallet_labels: "wallet_labels"
        smart_money_profiles: "smart_money_profiles"
        exchange_addresses: "exchange_addresses"
    redis:
      url: "${REDIS_URL}"
      key_prefix: "whale:"
      score_cache_ttl_seconds: 300     # Cache whale_activity_score for 5 min
      label_cache_ttl_days: 7

  # Kafka output
  kafka:
    bootstrap_servers: "${KAFKA_BOOTSTRAP_SERVERS}"
    topic: "whale-activity"
    key_serializer: "org.apache.kafka.common.serialization.StringSerializer"
    value_serializer: "org.apache.kafka.common.serialization.ByteArraySerializer"

  # Monitoring cadence per chain
  monitoring_cadence:
    ethereum: "every_block"
    solana: "every_5_slots"
    bitcoin: "every_block"
    polygon: "every_2_blocks"
    arbitrum: "every_10_blocks"

  # Rate limiting for external APIs
  rate_limits:
    etherscan_calls_per_second: 5
    whale_alert_calls_per_minute: 100
    nansen_calls_per_minute: 60
    rpc_calls_per_second: 100
```

## Database Schema

### PostgreSQL Tables

```sql
-- Whale movements (append-only, partitioned by month)
CREATE TABLE whale_movements (
    movement_id     TEXT PRIMARY KEY,
    chain           TEXT NOT NULL,
    tx_hash         TEXT NOT NULL,
    from_address    TEXT NOT NULL,
    to_address      TEXT NOT NULL,
    token           TEXT NOT NULL,
    amount          NUMERIC NOT NULL,
    usd_value       NUMERIC NOT NULL,
    block_number    BIGINT NOT NULL,
    block_timestamp TIMESTAMPTZ NOT NULL,
    movement_type   TEXT NOT NULL,
    from_entity     TEXT,
    to_entity       TEXT,
    impact_score    DOUBLE PRECISION,
    is_smart_money  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (block_timestamp);

CREATE INDEX idx_whale_movements_token_time
    ON whale_movements (token, block_timestamp DESC);
CREATE INDEX idx_whale_movements_from
    ON whale_movements (from_address, block_timestamp DESC);
CREATE INDEX idx_whale_movements_to
    ON whale_movements (to_address, block_timestamp DESC);
CREATE INDEX idx_whale_movements_type
    ON whale_movements (movement_type, block_timestamp DESC);

-- Wallet labels
CREATE TABLE wallet_labels (
    address       TEXT NOT NULL,
    chain         TEXT NOT NULL,
    entity_name   TEXT,
    wallet_type   TEXT NOT NULL,
    is_exchange   BOOLEAN DEFAULT FALSE,
    is_smart_money BOOLEAN DEFAULT FALSE,
    source        TEXT,                    -- "etherscan", "nansen", "manual"
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (address, chain)
);

-- Smart money profiles (refreshed periodically)
CREATE TABLE smart_money_profiles (
    address        TEXT PRIMARY KEY,
    win_rate       DOUBLE PRECISION,
    avg_return     DOUBLE PRECISION,
    total_trades   INTEGER,
    lookback_days  INTEGER,
    confidence     DOUBLE PRECISION,
    last_computed  TIMESTAMPTZ DEFAULT NOW(),
    next_refresh   TIMESTAMPTZ
);

CREATE INDEX idx_smart_money_win_rate
    ON smart_money_profiles (win_rate DESC)
    WHERE confidence > 0.5;

-- Exchange addresses (reference table)
CREATE TABLE exchange_addresses (
    address       TEXT PRIMARY KEY,
    chain         TEXT NOT NULL,
    entity_name   TEXT NOT NULL,
    active        BOOLEAN DEFAULT TRUE,
    added_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### InfluxDB Measurements

```
# Individual whale movements (high-resolution)
whale_movement,chain=ethereum,token=ETH,type=exchange_inflow usd_value=5200000,amount=2100,impact_score=0.72 1707840000000000000

# Aggregated whale activity score (per token, every 5 min)
whale_activity_score,token=ETH score=0.35,bullish_pressure=0.25,bearish_pressure=0.65,movement_count=12 1707840000000000000

# Exchange flow totals (per token, per direction)
exchange_flow,token=ETH,direction=inflow usd_total=15200000,count=5 1707840000000000000
exchange_flow,token=ETH,direction=outflow usd_total=8100000,count=3 1707840000000000000
```

## Constraints

- Detection latency must meet chain-specific targets (see Latency Targets table above).
- Must handle chain reorganizations (reorgs) gracefully: re-process affected blocks, do not double-count movements.
- Deduplication across data sources: the same on-chain transaction must not be scored multiple times regardless of how many sources report it.
- External API failures must not halt the pipeline; degrade gracefully by using cached data or skipping the enrichment step.
- Smart money profile computation must not block the real-time pipeline; profiles are precomputed and cached.
- Wallet label resolution has a hard timeout of 500ms per address; fall back to "Unknown" on timeout.
- Total monthly external API cost must not exceed $500 in the initial deployment (cost-optimized stack).
- The `whale_activity_score` must be available in Redis within 5 minutes of the underlying on-chain movement.
- PostgreSQL whale_movements table must be partitioned by month with a 90-day retention policy.

## Non-Goals

- **Trade execution**: This system detects and scores whale movements; it does not execute trades.
- **Cross-chain aggregation**: Movements are scored per-token per-chain. Cross-chain aggregation (e.g., total ETH movements across Ethereum + Arbitrum) is a future enhancement.
- **Wallet de-anonymization**: We label wallets with known entities (exchanges, protocols) but do not attempt to de-anonymize unknown wallets beyond on-chain analytics provider labels.
- **Historical backfill at launch**: The pipeline processes real-time data from launch forward. Historical backfill of whale movements is a separate effort.
- **NFT whale tracking**: Only fungible token movements are tracked. NFT whale activity is out of scope.
- **Social signal fusion**: Correlating whale movements with social media sentiment (e.g., tweets from known whale wallets) is a future enhancement, not part of this spec.

## Acceptance Criteria

- [ ] Pipeline detects whale movements on Ethereum within 1 block (~15 seconds)
- [ ] Pipeline detects whale movements on Solana within 5 slots (~2 seconds)
- [ ] Movements are classified into correct MovementType with >90% accuracy (validated against manually labeled test set)
- [ ] `whale_activity_score` is computed per token on a 1-hour sliding window with 5-minute slides
- [ ] `whale_activity_score` is published to Kafka topic `whale-activity` and cached in Redis
- [ ] Opportunity Scorer consumes `whale_activity_score` and applies the 10% weight factor
- [ ] Exchange inflow > 5% of daily volume suppresses BUY opportunity score by 15%
- [ ] Exchange outflow > 5% of daily volume boosts BUY opportunity score by 10%
- [ ] Smart money wallets (>60% win rate, >10 trades) receive amplified weight (1.5-2.0x)
- [ ] Smart money profiles are refreshed on schedule (6h/24h/7d by category)
- [ ] Deduplication prevents the same transaction from being scored twice across sources
- [ ] Chain reorg handling: affected movements are invalidated and reprocessed
- [ ] External API failures degrade gracefully (pipeline continues with reduced enrichment)
- [ ] Wallet label resolution has a 500ms timeout with fallback to "Unknown"
- [ ] All whale movements are persisted to InfluxDB (time-series) and PostgreSQL (relational)
- [ ] Prometheus metrics are emitted for movement counts, latency, score distribution, and API health
- [ ] Monthly external API cost stays within $500 budget (cost-optimized tier)
- [ ] Configuration is externalized via YAML with per-chain, per-token overrides

## Implementing Issues

| Issue | Status | Description |
|-------|--------|-------------|
| #TBD  | open   | Set up whale monitoring protobuf definitions |
| #TBD  | open   | Implement Ethereum block reader for Beam pipeline |
| #TBD  | open   | Implement Solana block reader for Beam pipeline |
| #TBD  | open   | Implement movement classifier DoFn |
| #TBD  | open   | Implement impact scorer DoFn |
| #TBD  | open   | Implement whale activity aggregator (windowed combine) |
| #TBD  | open   | Build exchange address registry with database backing |
| #TBD  | open   | Integrate Whale Alert API as data source |
| #TBD  | open   | Build smart money tracker with profile refresh scheduler |
| #TBD  | open   | Integrate whale_activity_score into opportunity scorer |
| #TBD  | open   | Add PostgreSQL schema and migrations |
| #TBD  | open   | Add InfluxDB measurements and Grafana dashboards |
| #TBD  | open   | Add Kafka topic configuration and consumer setup |
| #TBD  | open   | Helm chart updates for whale monitoring service |

## File Structure

```
src/main/java/com/verlumen/tradestream/whale/
|-- WhaleMonitoringPipeline.java         # Main Beam pipeline
|-- WhaleMonitoringModule.java           # Guice module
|-- WhaleMonitoringConfig.java           # Configuration POJO
|-- MovementClassifier.java              # Movement type classification
|-- ImpactScorer.java                    # Per-movement impact scoring
|-- SmartMoneyTracker.java               # Smart money profiling
|-- WhaleActivityAggregator.java         # Windowed aggregation
|-- ExchangeAddressRegistry.java         # Exchange address lookup
|-- WalletLabelEnricher.java             # Beam DoFn for wallet enrichment
|-- readers/
|   |-- EthereumBlockReader.java         # Ethereum RPC block reader
|   |-- SolanaBlockReader.java           # Solana RPC block reader
|   |-- WhaleAlertReader.java            # Whale Alert API poller
|   |-- BitcoinBlockReader.java          # Bitcoin RPC block reader
|-- writers/
|   |-- InfluxDBWriter.java              # InfluxDB sink
|   |-- PostgresMovementWriter.java      # PostgreSQL sink
|   |-- RedisCacheWriter.java            # Redis score cache writer
|   |-- KafkaActivityWriter.java         # Kafka producer
|-- BUILD

src/test/java/com/verlumen/tradestream/whale/
|-- MovementClassifierTest.java
|-- ImpactScorerTest.java
|-- SmartMoneyTrackerTest.java
|-- WhaleActivityAggregatorTest.java
|-- ExchangeAddressRegistryTest.java
|-- WalletLabelEnricherTest.java
|-- BUILD

protos/
|-- whale_monitoring.proto               # Protobuf definitions

charts/tradestream/templates/
|-- whale-monitoring-deployment.yaml     # K8s deployment
|-- whale-monitoring-configmap.yaml      # Configuration

config/
|-- whale-monitoring.yaml                # Default configuration
```

## Metrics

```
# Counters
whale_movements_detected_total{chain, token, type}
whale_movements_classified_total{chain, type}
whale_movements_deduplicated_total{chain}
whale_api_calls_total{provider, status}
whale_api_errors_total{provider, error_type}
wallet_label_lookups_total{source, result}   # source=registry|cache|api, result=hit|miss|timeout
smart_money_profiles_computed_total
reorg_events_handled_total{chain}
opportunity_score_whale_adjustments_total{direction}  # suppressed|boosted

# Gauges
whale_activity_score{token}
whale_movements_in_window{token}
exchange_inflow_usd_1h{token}
exchange_outflow_usd_1h{token}
smart_money_tracked_wallets
exchange_addresses_loaded
api_rate_limit_remaining{provider}

# Histograms
whale_movement_detection_latency_ms{chain}
whale_movement_end_to_end_latency_ms{chain}
whale_impact_score_distribution{token}
wallet_label_resolution_ms{source}
smart_money_profile_computation_ms
whale_activity_aggregation_ms{token}
```

## Notes

### Alternatives Considered

1. **Polling vs. WebSocket for block data**: WebSocket subscriptions (`newHeads`, `logs`) provide lower latency than polling. However, WebSocket connections are less reliable (disconnections, missed messages). The pipeline uses WebSocket as primary with polling as fallback to ensure no blocks are missed.

2. **Single aggregated score vs. per-movement signals**: We chose a single `whale_activity_score` per token rather than forwarding every individual movement to the opportunity scorer. This reduces downstream complexity and noise. Individual movements are still persisted for analysis and debugging.

3. **Nansen vs. Arkham for smart money labels**: Nansen was chosen over Arkham because Nansen provides API access at the Explorer tier ($150/mo), while Arkham requires an enterprise contract for API access. Both provide comparable entity labeling quality.

4. **Sliding window vs. tumbling window for aggregation**: A sliding window (1h window, 5m slide) was chosen over a tumbling window because it provides smoother score transitions. A tumbling window would cause abrupt score changes at window boundaries, which could create false signals.

### Dependencies

- Requires the existing Kafka infrastructure to be available for the `whale-activity` topic.
- Requires InfluxDB to be configured with a `whale_movements` bucket.
- Requires PostgreSQL schema migrations to be run before pipeline start.
- The Opportunity Scorer agent spec must be updated to consume `whale_activity_score` from Redis/Kafka.
- Exchange address seed data must be loaded into PostgreSQL before the pipeline is useful. An initial dataset of ~50,000 known exchange addresses will be sourced from Etherscan labels + community-maintained lists.

### Future Enhancements

- Cross-chain aggregation of whale activity per token (e.g., all ETH movements across Ethereum, Arbitrum, Optimism).
- Correlation of whale movements with social media signals from the same entity.
- Machine learning model for movement classification (replacing rule-based classifier) once sufficient labeled training data is collected.
- Historical backfill pipeline for building smart money profiles from archival blockchain data.
- Real-time whale alert notifications to users via the multi-channel delivery system.
