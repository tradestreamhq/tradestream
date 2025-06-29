package com.verlumen.tradestream.marketdata;

import com.google.common.flogger.FluentLogger;
import org.apache.beam.sdk.coders.*;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.transforms.Combine;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.windowing.SlidingWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Duration;

/**
 * SlidingCandleAggregator aggregates Trade messages into a Candle per sliding window. The input is
 * a PCollection of KV<String, Trade> keyed by currency pair (e.g. "BTC/USD").
 */
public class SlidingCandleAggregator
    extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, Candle>>> {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private final Duration windowDuration;
  private final Duration slideDuration;

  public SlidingCandleAggregator(Duration windowDuration, Duration slideDuration) {
    this.windowDuration = windowDuration;
    this.slideDuration = slideDuration;
  }

  @Override
  public PCollection<KV<String, Candle>> expand(PCollection<KV<String, Trade>> input) {
    logger.atInfo().log(
        "Starting SlidingCandleAggregator. WindowDuration=%s, SlideDuration=%s, Input=%s",
        windowDuration, slideDuration, input);

    // Apply sliding window.
    PCollection<KV<String, Trade>> windowed =
        input.apply(
            "ApplySlidingWindow",
            Window.<KV<String, Trade>>into(SlidingWindows.of(windowDuration).every(slideDuration)));
    logger.atFine().log("Applied sliding window. Output PCollection: %s", windowed);

    // Aggregate trades into Candles per key using the now external CandleCombineFn.
    // The BUILD file will need to make CandleCombineFn available here.
    PCollection<KV<String, Candle>> output =
        windowed.apply(
            "AggregateToCandle",
            Combine.perKey(new CandleCombineFn()) // Use the external CandleCombineFn
            );
    logger.atFine().log(
        "Applied Combine.perKey with external CandleCombineFn. Output PCollection: %s", output);

    // Set coder for the output.
    output.setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle.class)));
    logger.atInfo().log("Set KvCoder on output. Final output coder: %s", output.getCoder());

    logger.atInfo().log("Finished SlidingCandleAggregator. Returning output: %s", output);
    return output;
  }
}
