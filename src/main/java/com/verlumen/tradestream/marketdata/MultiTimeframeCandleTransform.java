package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.time.TimeFrame;
import java.util.ArrayList;
import java.util.List;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;

/**
 * MultiTimeframeCandleTransform branches a consolidated base candle stream into multiple
 * timeframe views. For each timeframe defined in the TimeFrame enum, it applies a buffering
 * transform (LastCandlesFn.BufferLastCandles) with a buffer size equal to the number of minutes
 * specified. The resulting branches are flattened into one output collection.
 *
 * This transform assumes that the input is a consolidated candle stream (for example, from
 * CandleStreamWithDefaults) where each key appears only once.
 */
public class MultiTimeframeCandleTransform 
    extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
      List<PCollection<KV<String, ImmutableList<Candle>>>> branches = new ArrayList<>();

      // Loop over each timeframe defined in the TimeFrame enum.
      for (TimeFrame tf : TimeFrame.values()) {
          // Use the timeframe's label to name the branch (e.g., "5mCandles", "1hCandles", etc.)
          String branchName = tf.getLabel() + "Candles";
          // The buffer size is defined by the timeframe's minutes.
          int bufferSize = tf.getMinutes();

          // For each branch, apply the buffering transform.
          PCollection<KV<String, ImmutableList<Candle>>> branch =
              input.apply(branchName, ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)));
          branches.add(branch);
      }
      
      // Flatten all branches into one output collection.
      return PCollectionList.of(branches)
              .apply("FlattenTimeframes", Flatten.pCollections());
  }
}
