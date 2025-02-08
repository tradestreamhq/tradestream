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
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;
import org.joda.time.Duration;
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.transforms.windowing.Window;

/**
 * CandleStreamWithDefaults is a composite transform that:
 * 
 *  1. Generates synthetic default trades for a list of currency pairs using DefaultTradeGenerator.
 *  2. Reshuffles and unions real trades with synthetic trades.
 *  3. Aggregates trades into candles via SlidingCandleAggregator.
 *  4. Re-windows the aggregated candle stream into a GlobalWindow.
 *  5. Buffers the last N candles per key via LastCandlesFn.BufferLastCandles.
 *  6. Groups by key to consolidate multiple outputs into one output per key.
 * 
 * For keys that have no real trades, the default trade is used to trigger candle creation
 * (producing a default candle with all zero values). Duplicate default candles are deduplicated
 * in LastCandlesFn.
 */
public class CandleStreamWithDefaults extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {

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
            .apply("ReshardDefault", Reshuffle.viaRandomKey());

        // 3. Reshard real trades.
        PCollection<KV<String, Trade>> realTrades = input.apply("ReshardRealTrades", Reshuffle.viaRandomKey());

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

        // 7. Group by key to consolidate outputs from multiple sliding windows into one element per key.
        PCollection<KV<String, Iterable<ImmutableList<Candle>>>> grouped = buffered.apply("GroupByKey", GroupByKey.create());
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
