package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.util.List;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.Reshuffle;
import org.apache.beam.sdk.transforms.SimpleFunction;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.transforms.windowing.SlidingWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;
import org.joda.time.Duration;

/**
 * CandleStreamWithDefaults is a composite transform that:
 * 
 *  1. Generates synthetic default trades for a list of currency pairs using DefaultTradeGenerator.
 *  2. Reshuffles and unions real trades with synthetic trades.
 *  3. Aggregates trades into candles via SlidingCandleAggregator.
 *  4. Re-windows the aggregated candle stream into a GlobalWindow.
 *  5. Buffers the last N candles per key via LastCandlesFn.BufferLastCandles.
 *  6. Re-windows the buffered output into SlidingWindows for consistent grouping.
 *  7. Groups by key to consolidate multiple outputs into one output per key.
 * 
 * For keys that have no real trades, the default trade is used to trigger candle creation
 * (producing a default candle with all zero values). Duplicate default candles are deduplicated
 * in LastCandlesFn.
 * 
 * Buffer Size Considerations:
 * - The buffer size determines how many historical candles are kept for each currency pair
 * - A larger buffer size provides more historical context for technical analysis
 * - A smaller buffer size reduces memory usage and latency
 * - The buffer size should be at least 1 and not exceed reasonable memory limits
 * - For 1-minute candles, a buffer size of 1440 would provide 24 hours of history
 */
public class CandleStreamWithDefaults extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {

    private static final int MIN_BUFFER_SIZE = 1;
    private static final int MAX_BUFFER_SIZE = 10000; // Reasonable upper limit for memory safety
    private static final Duration MIN_WINDOW_DURATION = Duration.standardSeconds(1);
    private static final Duration MAX_WINDOW_DURATION = Duration.standardHours(24);
    private static final Duration MIN_SLIDE_DURATION = Duration.standardSeconds(1);
    private static final double MIN_DEFAULT_PRICE = 0.0001; // Minimum reasonable price for crypto
    private static final int MAX_CURRENCY_PAIRS = 100; // Maximum number of currency pairs to prevent memory issues
    private static final double MAX_DEFAULT_PRICE = 1_000_000_000.0; // Maximum reasonable price for crypto
    private static final int MAX_WINDOW_SLIDE_RATIO = 1000; // Maximum ratio between window and slide duration
    private static final int MIN_WINDOW_SLIDE_RATIO = 2; // Minimum ratio between window and slide duration

    private final Duration windowDuration;
    private final Duration slideDuration;
    private final int bufferSize;
    private final List<String> currencyPairs;
    private final double defaultPrice;

    public CandleStreamWithDefaults(Duration windowDuration, Duration slideDuration, int bufferSize, List<String> currencyPairs, double defaultPrice) {
        // Validate window duration
        if (windowDuration == null) {
            throw new IllegalArgumentException("Window duration cannot be null");
        }
        if (windowDuration.getMillis() < MIN_WINDOW_DURATION.getMillis()) {
            throw new IllegalArgumentException(
                String.format("Window duration must be at least %d seconds", MIN_WINDOW_DURATION.getStandardSeconds()));
        }
        if (windowDuration.getMillis() > MAX_WINDOW_DURATION.getMillis()) {
            throw new IllegalArgumentException(
                String.format("Window duration cannot exceed %d hours", MAX_WINDOW_DURATION.getStandardHours()));
        }

        // Validate slide duration
        if (slideDuration == null) {
            throw new IllegalArgumentException("Slide duration cannot be null");
        }
        if (slideDuration.getMillis() < MIN_SLIDE_DURATION.getMillis()) {
            throw new IllegalArgumentException(
                String.format("Slide duration must be at least %d second", MIN_SLIDE_DURATION.getStandardSeconds()));
        }
        if (slideDuration.getMillis() > windowDuration.getMillis()) {
            throw new IllegalArgumentException("Slide duration cannot be greater than window duration");
        }

        // Validate buffer size
        if (bufferSize < MIN_BUFFER_SIZE || bufferSize > MAX_BUFFER_SIZE) {
            throw new IllegalArgumentException(
                String.format("Buffer size must be between %d and %d", MIN_BUFFER_SIZE, MAX_BUFFER_SIZE));
        }

        // Validate currency pairs
        if (currencyPairs == null) {
            throw new IllegalArgumentException("Currency pairs list cannot be null");
        }
        if (currencyPairs.isEmpty()) {
            throw new IllegalArgumentException("Currency pairs list cannot be empty");
        }
        if (currencyPairs.size() > MAX_CURRENCY_PAIRS) {
            throw new IllegalArgumentException(
                String.format("Too many currency pairs: %d. Maximum allowed is %d", 
                    currencyPairs.size(), MAX_CURRENCY_PAIRS));
        }
        for (String pair : currencyPairs) {
            if (pair == null || pair.trim().isEmpty()) {
                throw new IllegalArgumentException("Currency pair cannot be null or empty");
            }
            if (!pair.matches("^[A-Z0-9]+/[A-Z0-9]+$")) {
                throw new IllegalArgumentException(
                    String.format("Invalid currency pair format: %s. Expected format: BASE/QUOTE (e.g., BTC/USD)", pair));
            }
            // Check for duplicate currency pairs (case-insensitive)
            String normalizedPair = pair.toUpperCase();
            if (currencyPairs.stream()
                    .filter(p -> p.toUpperCase().equals(normalizedPair))
                    .count() > 1) {
                throw new IllegalArgumentException(
                    String.format("Duplicate currency pair found: %s", pair));
            }
        }

        // Validate default price
        if (defaultPrice <= 0) {
            throw new IllegalArgumentException("Default price must be positive");
        }
        if (defaultPrice < MIN_DEFAULT_PRICE) {
            throw new IllegalArgumentException(
                String.format("Default price must be at least %.4f", MIN_DEFAULT_PRICE));
        }
        if (defaultPrice > MAX_DEFAULT_PRICE) {
            throw new IllegalArgumentException(
                String.format("Default price cannot exceed %.2f", MAX_DEFAULT_PRICE));
        }

        // Validate window/slide ratio
        long ratio = windowDuration.getMillis() / slideDuration.getMillis();
        if (ratio < MIN_WINDOW_SLIDE_RATIO) {
            throw new IllegalArgumentException(
                String.format("Window duration (%d ms) is too small compared to slide duration (%d ms). " +
                    "This would create too few overlapping windows.", 
                    windowDuration.getMillis(), slideDuration.getMillis()));
        }
        if (ratio > MAX_WINDOW_SLIDE_RATIO) {
            throw new IllegalArgumentException(
                String.format("Window duration (%d ms) is too large compared to slide duration (%d ms). " +
                    "This would create too many overlapping windows.", 
                    windowDuration.getMillis(), slideDuration.getMillis()));
        }

        // Validate memory usage
        long estimatedMemoryPerPair = (long) bufferSize * 100; // Rough estimate of memory per candle in bytes
        long totalEstimatedMemory = estimatedMemoryPerPair * currencyPairs.size();
        if (totalEstimatedMemory > 1_000_000_000) { // 1GB limit
            throw new IllegalArgumentException(
                String.format("Estimated memory usage (%.2f GB) exceeds 1GB limit. Consider reducing buffer size or number of currency pairs.",
                    totalEstimatedMemory / (1024.0 * 1024.0 * 1024.0)));
        }

        this.windowDuration = windowDuration;
        this.slideDuration = slideDuration;
        this.bufferSize = bufferSize;
        this.currencyPairs = ImmutableList.copyOf(currencyPairs); // Make immutable
        this.defaultPrice = defaultPrice;
    }

    @Override
    public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Trade>> input) {
        // 1. Create keys for all currency pairs.
        PCollection<KV<String, Void>> keys = input.getPipeline()
            .apply("CreateCurrencyPairKeys", Create.of(currencyPairs))
            .apply("PairWithVoid", MapElements.via(new SimpleFunction<String, KV<String, Void>>() {
                @Override
                public KV<String, Void> apply(String input) {
                    return KV.of(input, null);
                }
            }));

        // 2. Generate synthetic default trades.
        PCollection<KV<String, Trade>> defaultTrades = keys
            .apply("GenerateDefaultTrades", new DefaultTradeGenerator(defaultPrice))
            .apply("ReshardDefault", Reshuffle.viaRandomKey())
            // Use SlidingWindows for default trades to match the real trades
            .apply("RewindowDefaultTrades", Window.<KV<String, Trade>>into(
                SlidingWindows.of(windowDuration).every(slideDuration)));

        // 3. Reshard real trades and force them into the same SlidingWindows
        PCollection<KV<String, Trade>> realTrades = input
            .apply("ReshardRealTrades", Reshuffle.viaRandomKey())
            .apply("RewindowRealTrades", Window.<KV<String, Trade>>into(
                SlidingWindows.of(windowDuration).every(slideDuration)));

        // 4. Flatten real and default trades
        PCollection<KV<String, Trade>> allTrades = PCollectionList.of(realTrades).and(defaultTrades)
            .apply("FlattenTrades", Flatten.pCollections());

        // 5. Aggregate trades into candles using sliding windows
        PCollection<KV<String, Candle>> candles = allTrades.apply("AggregateCandles",
            new SlidingCandleAggregator(windowDuration, slideDuration));

        // 5.1 Re-window aggregated candles into a GlobalWindow for buffering
        PCollection<KV<String, Candle>> globalCandles =
            candles.apply("RewindowToGlobal", Window.<KV<String, Candle>>into(new GlobalWindows()));

        // 6. Buffer last N candles per key
        PCollection<KV<String, ImmutableList<Candle>>> buffered =
            globalCandles.apply("BufferLastCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)));

        // 7. Re-window the buffered output into SlidingWindows for consistent grouping
        PCollection<KV<String, ImmutableList<Candle>>> rewindowedBuffered =
            buffered.apply("RewindowBuffered", 
                Window.<KV<String, ImmutableList<Candle>>>into(
                    SlidingWindows.of(windowDuration).every(slideDuration)));
        
        // 8. Group by key to consolidate outputs from multiple windows into one element per key
        PCollection<KV<String, Iterable<ImmutableList<Candle>>>> grouped = rewindowedBuffered.apply("GroupByKey", GroupByKey.create());
        PCollection<KV<String, ImmutableList<Candle>>> finalOutput =
            grouped.apply("ExtractLastBuffered", MapElements.via(new SimpleFunction<KV<String, Iterable<ImmutableList<Candle>>>, KV<String, ImmutableList<Candle>>>() {
                @Override
                public KV<String, ImmutableList<Candle>> apply(KV<String, Iterable<ImmutableList<Candle>>> input) {
                    ImmutableList<Candle> last = null;
                    for (ImmutableList<Candle> list : input.getValue()) {
                        last = list; // Iterate and take the last list.
                    }
                    return KV.of(input.getKey(), last);
                }
            }));
        return finalOutput;
    }
}
