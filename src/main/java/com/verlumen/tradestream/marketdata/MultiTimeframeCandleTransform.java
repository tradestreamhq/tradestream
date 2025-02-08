package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.time.TimeFrame;
import java.util.ArrayList;
import java.util.List;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.SimpleFunction;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;

/**
 * MultiTimeframeCandleTransform branches a consolidated base candle stream into multiple
 * timeframe views. For each timeframe defined in the TimeFrame enum, it applies a buffering
 * transform (LastCandlesFn.BufferLastCandles) with a buffer size equal to the number of minutes
 * specified. The resulting branches are flattened into one output collection.
 *
 * This transform first groups the input by key so that each key appears only once.
 */
public class MultiTimeframeCandleTransform 
    extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
      // Group by key to consolidate multiple Candle elements per key.
      PCollection<KV<String, Iterable<Candle>>> grouped = input.apply("GroupByKey", GroupByKey.create());

      // Consolidate each key's Iterable<Candle> into a single Candle.
      // For simplicity, we pick the last element from the iterable.
      PCollection<KV<String, Candle>> consolidated = grouped.apply("ConsolidateCandles",
          ParDo.of(new DoFn<KV<String, Iterable<Candle>>, KV<String, Candle>>() {
              @ProcessElement
              public void processElement(ProcessContext c) {
                  KV<String, Iterable<Candle>> element = c.element();
                  Candle last = null;
                  for (Candle candle : element.getValue()) {
                      last = candle;
                  }
                  if (last != null) {
                      c.output(KV.of(element.getKey(), last));
                  }
              }
          }));

      // Create branches for each timeframe defined in the TimeFrame enum.
      List<PCollection<KV<String, ImmutableList<Candle>>>> branches = new ArrayList<>();
      for (TimeFrame tf : TimeFrame.values()) {
          // Use the timeframe's label to name the branch (e.g., "5mCandles", "1hCandles", etc.)
          String branchName = tf.getLabel() + "Candles";
          // The buffer size is defined by the timeframe's minutes.
          int bufferSize = tf.getMinutes();
          // Apply the buffering transform.
          PCollection<KV<String, ImmutableList<Candle>>> branch =
              consolidated.apply(branchName, ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)));
          branches.add(branch);
      }

      // Flatten all branches into one output collection.
      return PCollectionList.of(branches)
              .apply("FlattenTimeframes", Flatten.pCollections());
  }
}
