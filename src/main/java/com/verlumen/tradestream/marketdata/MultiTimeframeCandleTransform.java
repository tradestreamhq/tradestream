package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;

/**
 * MultiTimeframeCandleTransform branches a base candle stream into multiple timeframes.
 * Each branch applies the stateful buffering transform (LastCandlesFn.BufferLastCandles) with a
 * specific buffer size, representing the desired timeframe. The outputs of all branches are then
 * flattened into a single PCollection.
 *
 * Note: This transform assumes that the input is a consolidated base candle stream (e.g. the output
 * of CandleStreamWithDefaults) where each key appears only once.
 */
public class MultiTimeframeCandleTransform 
    extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {

    @Override
    public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
        // Branch 1: 5-minute timeframe (buffer size = 5)
        PCollection<KV<String, ImmutableList<Candle>>> fiveMinCandles =
                input.apply("5MinCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(5)));
        
        // Branch 2: 15-minute timeframe (buffer size = 15)
        PCollection<KV<String, ImmutableList<Candle>>> fifteenMinCandles =
                input.apply("15MinCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(15)));
        
        // Branch 3: 30-minute timeframe (buffer size = 30)
        PCollection<KV<String, ImmutableList<Candle>>> thirtyMinCandles =
                input.apply("30MinCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(30)));
        
        // Branch 4: Hourly timeframe (buffer size = 60)
        PCollection<KV<String, ImmutableList<Candle>>> hourlyCandles =
                input.apply("HourlyCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(60)));
        
        // Branch 5: Daily timeframe (buffer size = 390)
        PCollection<KV<String, ImmutableList<Candle>>> dailyCandles =
                input.apply("DailyCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(390)));
        
        // Flatten all branches into one output collection.
        return PCollectionList.of(fiveMinCandles)
                .and(fifteenMinCandles)
                .and(thirtyMinCandles)
                .and(hourlyCandles)
                .and(dailyCandles)
                .apply("FlattenTimeframes", Flatten.pCollections());
    }
}
