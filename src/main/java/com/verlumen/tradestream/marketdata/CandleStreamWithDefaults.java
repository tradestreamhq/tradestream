package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.util.List;
import java.util.Arrays;
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
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.transforms.windowing.AfterProcessingTime;
import org.apache.beam.sdk.transforms.windowing.Repeatedly;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;
import org.joda.time.Duration;
import com.google.common.flogger.FluentLogger;

/**
 * CandleStreamWithDefaults is a composite transform that:
 * 
 *  1. Generates synthetic default trades for a list of currency pairs using DefaultTradeGenerator.
 *  2. Reshuffles and unions real trades with synthetic trades.
 *  3. Aggregates trades into candles via SlidingCandleAggregator.
 *  4. Re-windows the aggregated candle stream into a GlobalWindow.
 *  5. Buffers the last N candles per key via LastCandlesFn.BufferLastCandles.
 *  6. Re-windows the buffered output into a FixedWindow (here, 1 day) so that GroupByKey can be applied.
 *  7. Groups by key to consolidate multiple outputs into one output per key.
 * 
 * For keys that have no real trades, the default trade is used to trigger candle creation
 * (producing a default candle with all zero values). Duplicate default candles are deduplicated
 * in LastCandlesFn.
 */
public class CandleStreamWithDefaults extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {

    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final Duration windowDuration;
    private final Duration slideDuration;
    private final int bufferSize;
    private final List<String> currencyPairs;
    private final double defaultPrice;

    public CandleStreamWithDefaults(Duration windowDuration, Duration slideDuration, int bufferSize, List<String> currencyPairs, double defaultPrice) {
        this.windowDuration = windowDuration;
        this.slideDuration = slideDuration;
        this.bufferSize = bufferSize;
        this.currencyPairs = currencyPairs;
        this.defaultPrice = defaultPrice;
    }

    @Override
    public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Trade>> input) {
        logger.atInfo().log("CandleStreamWithDefaults: Starting transform expansion.");

        // 1. Create keys for all currency pairs.
        PCollection<KV<String, Void>> keys = input.getPipeline()
            .apply("CreateCurrencyPairKeys", Create.of(currencyPairs))
            .apply("PairWithVoid", MapElements.via(new SimpleFunction<String, KV<String, Void>>() {
                @Override
                public KV<String, Void> apply(String input) {
                    return KV.of(input, null);
                }
            }));
        logger.atInfo().log("CandleStreamWithDefaults: Created keys for currency pairs: %s", currencyPairs);
        
        // 2. Generate synthetic default trades.
        PCollection<KV<String, Trade>> defaultTrades = keys
            .apply("GenerateDefaultTrades", new DefaultTradeGenerator(defaultPrice))
            .apply("ReshardDefault", Reshuffle.viaRandomKey())
            .apply("RewindowDefaultTrades", Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration)));
        logger.atInfo().log("CandleStreamWithDefaults: Generated default trades.");
        
        // 3. Reshard real trades and force them into the same FixedWindows.
        PCollection<KV<String, Trade>> realTrades = input
            .apply("ReshardRealTrades", Reshuffle.viaRandomKey())
            .apply("RewindowRealTrades", Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration)));
        logger.atInfo().log("CandleStreamWithDefaults: Resharded real trades.");
        
        // 4. Flatten real and default trades.
        PCollection<KV<String, Trade>> allTrades = PCollectionList.of(realTrades).and(defaultTrades)
            .apply("FlattenTrades", Flatten.pCollections());
        logger.atInfo().log("CandleStreamWithDefaults: Flattened trades.");
        
        // 5. Aggregate trades into candles using sliding windows.
        PCollection<KV<String, Candle>> candles = allTrades.apply("AggregateCandles",
            new SlidingCandleAggregator(windowDuration, slideDuration));
        logger.atInfo().log("CandleStreamWithDefaults: Aggregated trades into candles.");
        
        // 5.1 Re-window aggregated candles into a GlobalWindow.
        PCollection<KV<String, Candle>> globalCandles =
            candles.apply("RewindowToGlobal", Window.<KV<String, Candle>>into(new GlobalWindows()));
        logger.atInfo().log("CandleStreamWithDefaults: Re-windowed candles into GlobalWindows.");
        
        // 6. Buffer last N candles per key.
        PCollection<KV<String, ImmutableList<Candle>>> buffered =
            globalCandles.apply("BufferLastCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)));
        logger.atInfo().log("CandleStreamWithDefaults: Buffered candles.");
        
        // 7. Re-window the buffered output into a FixedWindow (e.g., 1 day) with a trigger so that GroupByKey can fire.
        PCollection<KV<String, ImmutableList<Candle>>> rewindowedBuffered =
            buffered.apply("RewindowBuffered", 
                Window.<KV<String, ImmutableList<Candle>>>into(FixedWindows.of(Duration.standardDays(1)))
                      .triggering(Repeatedly.forever(AfterProcessingTime.pastFirstElementInPane().plusDelayOf(Duration.standardSeconds(1))))
                      .discardingFiredPanes()
                      .withAllowedLateness(Duration.ZERO)
            );
        logger.atInfo().log("CandleStreamWithDefaults: Re-windowed buffered candles into 1-day FixedWindows.");
        
        // 8. Group by key to consolidate outputs from multiple windows into one element per key.
        PCollection<KV<String, Iterable<ImmutableList<Candle>>>> grouped = rewindowedBuffered.apply("GroupByKey", GroupByKey.create());
        logger.atInfo().log("CandleStreamWithDefaults: Applied GroupByKey.");
        
        // 9. Combine all buffered lists into one final output.
        PCollection<KV<String, ImmutableList<Candle>>> finalOutput =
            grouped.apply("ExtractLastBuffered", MapElements.via(new SimpleFunction<KV<String, Iterable<ImmutableList<Candle>>>, KV<String, ImmutableList<Candle>>>() {
                @Override
                public KV<String, ImmutableList<Candle>> apply(KV<String, Iterable<ImmutableList<Candle>>> input) {
                    // Combine all buffered lists for this key.
                    ImmutableList.Builder<Candle> builder = ImmutableList.builder();
                    for (ImmutableList<Candle> list : input.getValue()) {
                        if (list != null) {
                            builder.addAll(list);
                        }
                    }
                    ImmutableList<Candle> combined = builder.build();
                    logger.atInfo().log("CandleStreamWithDefaults: Consolidated buffered list for key %s: %s", input.getKey(), combined);
                    return KV.of(input.getKey(), combined);
                }
            }));
        logger.atInfo().log("CandleStreamWithDefaults: Final output prepared.");
        return finalOutput;
    }
}
