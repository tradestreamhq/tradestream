package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;

/**
 * MultiTimeframeCandleTransform creates sliding-window views of a base candle stream
 * (where each candle is 1 minute in resolution) into multiple timeframes.
 *
 * For example:
 *  - A 1-hour view: last 60 candles (buffer size = 60)
 *  - A 1-day view: last 1440 candles (buffer size = 1440)
 *
 * Each branch applies a stateful buffering transform (LastCandlesFn.BufferLastCandles) with
 * the appropriate buffer size. The outputs of all branches are then flattened into a single
 * PCollection.
 *
 * This transform assumes that the input is a consolidated candle stream (for instance, as produced
 * by CandleStreamWithDefaults) where each key appears only once.
 */
public class MultiTimeframeCandleTransform 
    extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
      // Branch for 1-hour view: buffer the last 60 candles.
      PCollection<KV<String, ImmutableList<Candle>>> oneHourCandles =
          input.apply("OneHourCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(60)));
      
      // Branch for 1-day view: buffer the last 1440 candles.
      PCollection<KV<String, ImmutableList<Candle>>> oneDayCandles =
          input.apply("OneDayCandles", ParDo.of(new LastCandlesFn.BufferLastCandles(1440)));
      
      // (You can add more branches for additional timeframes if needed.)
      
      // Flatten all branches into one output collection.
      return PCollectionList.of(oneHourCandles)
                .and(oneDayCandles)
                .apply("FlattenTimeframes", Flatten.pCollections());
  }
}
