package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
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
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
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

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
    logger.atInfo().log("Starting MultiTimeframeCandleTransform expansion. Input: %s", input);

    // 1. Group by key to consolidate multiple Candle elements per key.
    logger.atInfo().log("Applying GroupByKey to consolidate Candle elements by key.");
    PCollection<KV<String, Iterable<Candle>>> grouped = input.apply("GroupByKey", GroupByKey.create());

    // 2. Consolidate each key's Iterable<Candle> into a single Candle.
    logger.atInfo().log("Consolidating each key's Iterable<Candle> into the latest Candle value.");
    PCollection<KV<String, Candle>> consolidated = grouped.apply("ConsolidateCandles",
        ParDo.of(new DoFn<KV<String, Iterable<Candle>>, KV<String, Candle>>() {

          @ProcessElement
          public void processElement(ProcessContext c) {
            KV<String, Iterable<Candle>> element = c.element();
            logger.atFine().log("Consolidating candles for key: %s. Iterable size unknown (stream).", element.getKey());

            Candle last = null;
            for (Candle candle : element.getValue()) {
              last = candle; 
            }
            if (last != null) {
              logger.atFine().log("Consolidation complete for key: %s. Last candle: %s", element.getKey(), last);
              c.output(KV.of(element.getKey(), last));
            } else {
              logger.atFine().log("No valid candle found to consolidate for key: %s", element.getKey());
            }
          }
        })
    );

    // 3. Create branches for each timeframe.
    logger.atInfo().log("Creating branches for each TimeFrame. Available timeframes: %s", TimeFrame.values());
    List<PCollection<KV<String, ImmutableList<Candle>>>> branches = new ArrayList<>();
    for (TimeFrame tf : TimeFrame.values()) {
      String branchName = tf.getLabel() + "Candles";
      int bufferSize = tf.getMinutes();

      logger.atInfo().log("Creating branch '%s' with bufferSize=%d (minutes).", branchName, bufferSize);

      PCollection<KV<String, ImmutableList<Candle>>> branch =
          consolidated
              .apply(
                  branchName,
                  ParDo.of(new LastCandlesFn.BufferLastCandles(bufferSize)))
              // 4. Re-window each branch into GlobalWindows.
              .apply("Rewindow_" + branchName, Window.<KV<String, ImmutableList<Candle>>>into(new GlobalWindows()));

      logger.atFine().log("Branch '%s' created and re-windowed into GlobalWindows.", branchName);
      branches.add(branch);
    }

    // 5. Flatten all branches into one output collection.
    logger.atInfo().log("Flattening %d branches into a single PCollection.", branches.size());
    PCollection<KV<String, ImmutableList<Candle>>> flattened =
        PCollectionList.of(branches).apply("FlattenTimeframes", Flatten.pCollections());

    logger.atInfo().log("Finished MultiTimeframeCandleTransform. Flattened output: %s", flattened);
    return flattened;
  }
}
