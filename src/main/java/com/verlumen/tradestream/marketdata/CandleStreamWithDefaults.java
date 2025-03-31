package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.google.inject.Inject;
import org.apache.beam.sdk.Pipeline;
import java.util.function.Supplier;
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
 *  6. Re-windows the buffered output into a FixedWindow (here, 1 day) so that GroupByKey can be applied.
 *  7. Groups by key to consolidate multiple outputs into one output per key.
 * 
 * For keys that have no real trades, the default trade is used to trigger candle creation
 * (producing a default candle with all zero values). Duplicate default candles are deduplicated
 * in LastCandlesFn.
 */
public class CandleStreamWithDefaults extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {

    private final Duration windowDuration;
    private final Duration slideDuration;
    private final int bufferSize;
    private final Supplier<ImmutableList<CurrencyPair>> currencyPairSupply;
    private final double defaultPrice;

    private CandleStreamWithDefaults(
        Duration windowDuration,
        Duration slideDuration,
        int bufferSize,
        Supplier<ImmutableList<CurrencyPair>> currencyPairSupply,
        double defaultPrice) {
        this.windowDuration = windowDuration;
        this.slideDuration = slideDuration;
        this.bufferSize = bufferSize;
        this.currencyPairSupply = currencyPairSupply;
        this.defaultPrice = defaultPrice;
    }

    @Override
    public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Trade>> input) {
        // 1. Create keys for all currency pairs.
        PCollection<KV<String, Void>> keys = input.getPipeline()
            .apply("CreateCurrencyPairKeys", Create.of(currencyPairSupply.get().stream().map(CurrencyPair::symbol).collect(toImmutableList())))
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
            // Force default trades into FixedWindows matching the real trades.
            .apply("RewindowDefaultTrades", Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration)));

        // 3. Reshard real trades and force them into the same FixedWindows.
        PCollection<KV<String, Trade>> realTrades = input
            .apply("ReshardRealTrades", Reshuffle.viaRandomKey())
            .apply("RewindowRealTrades", Window.<KV<String, Trade>>into(FixedWindows.of(windowDuration)));

        // 4. Flatten real and default trades.
        PCollection<KV<String, Trade>> allTrades = PCollectionList.of(realTrades).and(defaultTrades)
            .apply("FlattenTrades", Flatten.pCollections());

        // 5. Aggregate trades into candles using sliding windows.
        PCollection<KV<String, Candle>> candles = allTrades.apply("AggregateCandles",
            new SlidingCandleAggregator(windowDuration, slideDuration));

        // 5.1 Re-window aggregated candles into a GlobalWindow.
        PCollection<KV<String, Candle>> globalCandles =
            candles.apply("RewindowToGlobal", Window.<KV<String, Candle>>into(new GlobalWindows()));

        // 6. Buffer last N candles per key.
        PCollection<KV<String, ImmutableList<Candle>>> buffered =
            globalCandles.apply("BufferLastCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)));

        // 7. Re-window the buffered output into a FixedWindow (e.g., 1 day) so that GroupByKey can be applied.
        PCollection<KV<String, ImmutableList<Candle>>> rewindowedBuffered =
            buffered.apply("RewindowBuffered", 
                Window.<KV<String, ImmutableList<Candle>>>into(FixedWindows.of(Duration.standardDays(1))));
        
        // 8. Group by key to consolidate outputs from multiple windows into one element per key.
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

    public static class Factory {
        private static final int BUFFER_SIZE = 5;  // Buffer size for base candle consolidation.
        private static final Duration SLIDE_DURATION = Duration.standardSeconds(30);
        private static final double DEFAULT_SYNTHETIC_TRADE_PRICE = 10000.0;

        private final Supplier<ImmutableList<CurrencyPair>> currencyPairSupply;

        @Inject
        Factory(Supplier<ImmutableList<CurrencyPair>> currencyPairSupply) {
            this.currencyPairSupply = currencyPairSupply;
        }

        CandleStreamWithDefaults create(Duration windowDuration) {
            return new CandleStreamWithDefaults(
                windowDuration,
                SLIDE_DURATION,
                BUFFER_SIZE,  // Buffer size for base candle consolidation.
                Supplier<ImmutableList<CurrencyPair> currencyPairSupply,
                DEFAULT_SYNTHETIC_TRADE_PRICE);
        }
    }
}
