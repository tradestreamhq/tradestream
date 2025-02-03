package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.io.Serializable;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.windowing.SlidingWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.joda.time.Duration;

@AutoValue
public class GenerateMultiTimeframeSlidingCandles
    extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {
  public static GenerateMultiTimeframeSlidingCandles create(Duration slidePeriod) {
      return AutoValue_GenerateMultiTimeframeSlidingCandles(slidePeriod);
  }

  abstract Duration slidePeriod();

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Trade>> input) {
    PCollectionList<KV<String, ImmutableList<Candle>>> allTimeframes = 
        PCollectionList.empty(input.getPipeline());

    for (TimeFrame timeframe : TimeFrame.values()) {
      PCollection<KV<String, Trade>> windowedTrades = input.apply(
          "SlidingWindow " + timeframe.getLabel(),
          Window.<KV<String, Trade>>into(
              SlidingWindows.of(Duration.standardMinutes(timeframe.getMinutes()))
                            .every(slidePeriod()))
      );

      PCollection<KV<String, Iterable<Trade>>> groupedTrades = windowedTrades.apply(
          "GroupByKey " + timeframe.getLabel(),
          GroupByKey.create()
      );

      // Assume that GenerateCandles is your transform that aggregates trades into a Candle.
      PCollection<KV<String, Candle>> candles = groupedTrades.apply(
          "GenerateCandles " + timeframe.getLabel(),
          new GenerateCandles(timeframe)
      );

      PCollection<KV<String, ImmutableList<Candle>>> formattedCandles = candles.apply(
          "FormatCandles " + timeframe.getLabel(),
          MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(),
                                                 TypeDescriptors.lists(TypeDescriptors.classes(Candle.class))))
                     .via(kv -> KV.of(kv.getKey(), ImmutableList.of(kv.getValue())))
      );

      allTimeframes = allTimeframes.and(formattedCandles);
    }

    return allTimeframes.apply("Flatten All Timeframes", Flatten.pCollections());
  }
}
