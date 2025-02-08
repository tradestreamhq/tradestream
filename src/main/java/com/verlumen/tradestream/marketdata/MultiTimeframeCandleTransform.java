package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.time.TimeFrame;
import java.util.ArrayList;
import java.util.List;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.ProcessContext;
import org.apache.beam.sdk.transforms.DoFn.ProcessElement;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.SimpleFunction;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;

/**
 * MultiTimeframeCandleTransform branches a consolidated base candle stream into multiple
 * timeframe views. For each timeframe defined in the TimeFrame enum, it applies a buffering
 * transform (LastCandlesFn.BufferLastCandles) with a buffer size equal to the number of minutes
 * specified. Before flattening, each branch is explicitly re-windowed into GlobalWindows so that
 * all branches have the same windowing.
 *
 * This transform assumes that the input is a consolidated candle stream (for example, from
 * CandleStreamWithDefaults) where each key appears only once.
 */
public class MultiTimeframeCandleTransform 
    extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
      // Group by key to consolidate multiple Candle elements per key.
      PCollection<KV<String, Iterable<Candle>>> grouped = input.apply("GroupByKey", GroupByKey.create());

      // Consolidate each key's Iterable<Candle> into a single Candle.
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
          String branchName = tf.getLabel() + "Candles";
          int bufferSize = tf.getMinutes();
          // For each branch, apply the buffering transform.
          PCollection<KV<String, ImmutableList<Candle>>> branch =
              consolidated.apply(branchName, ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)))
                        // Force each branch to be in GlobalWindows.
                        .apply("Rewindow_" + branchName, Window.<KV<String, ImmutableList<Candle>>>into(new GlobalWindows()));
          branches.add(branch);
      }
      
      // Flatten all branches into one output collection.
      return PCollectionList.of(branches).apply("FlattenTimeframes", Flatten.pCollections());
  }
}
