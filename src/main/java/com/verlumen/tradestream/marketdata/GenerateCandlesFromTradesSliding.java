// File: GenerateCandlesFromTradesSliding.java
package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.Candle;
import java.io.Serializable;
import java.util.Arrays;
import org.apache.beam.sdk.transforms.Combine;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.windowing.SlidingWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.joda.time.Duration;

/**
 * A PTransform that aggregates Trade messages into Candles using sliding windows.
 * The input PCollection is keyed (for example, by currency pair), and the output is a
 * PCollection where each key maps to an ImmutableList of Candle messages (one per window).
 *
 * The transform uses a custom CombineFn (CandleCombineFn) to incrementally build a Candle
 * from Trade messages within each sliding window. This minimizes memory usage by retaining
 * only a small accumulator per key per window.
 */
public class GenerateCandlesFromTradesSliding
    extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, ImmutableList<Candle>>>> {

  private final Duration windowDuration;
  private final Duration slidePeriod;
  private final Duration allowedLateness;

  /**
   * @param windowDuration  the total duration of each window (e.g. 5 minutes)
   * @param slidePeriod     the period at which windows start (e.g. 1 minute)
   * @param allowedLateness allowed lateness for windowing (e.g. 1 minute)
   */
  public GenerateCandlesFromTradesSliding(Duration windowDuration, Duration slidePeriod, Duration allowedLateness) {
    this.windowDuration = windowDuration;
    this.slidePeriod = slidePeriod;
    this.allowedLateness = allowedLateness;
  }

  /**
   * An accumulator that holds the incremental state for a candle.
   */
  static class CandleAccumulator implements Serializable {
    double open = Double.NaN;
    double high = Double.NaN;
    double low = Double.NaN;
    double close = Double.NaN;
    double volume = 0.0;
    // The openTimestamp represents the timestamp of the first trade in the window.
    com.google.protobuf.Timestamp openTimestamp = null;
    String currencyPair = null;
  }

  /**
   * A CombineFn that incrementally aggregates Trade messages into a Candle.
   */
  public static class CandleCombineFn extends Combine.CombineFn<Trade, CandleAccumulator, Candle> {
    @Override
    public CandleAccumulator createAccumulator() {
      return new CandleAccumulator();
    }

    @Override
    public CandleAccumulator addInput(CandleAccumulator accumulator, Trade trade) {
      double price = trade.getPrice();
      double tradeVolume = trade.getVolume();
      String tradeCurrencyPair = trade.getCurrencyPair();
      com.google.protobuf.Timestamp tradeTimestamp = trade.getTimestamp();

      // If this is the first trade in the accumulator, initialize the values.
      if (Double.isNaN(accumulator.open)) {
        accumulator.open = price;
        accumulator.high = price;
        accumulator.low = price;
        accumulator.close = price;
        accumulator.volume = tradeVolume;
        accumulator.openTimestamp = tradeTimestamp;
        accumulator.currencyPair = tradeCurrencyPair;
      } else {
        accumulator.high = Math.max(accumulator.high, price);
        accumulator.low = Math.min(accumulator.low, price);
        accumulator.close = price; // update to the latest trade's price
        accumulator.volume += tradeVolume;
      }
      return accumulator;
    }

    @Override
    public CandleAccumulator mergeAccumulators(Iterable<CandleAccumulator> accumulators) {
      CandleAccumulator merged = createAccumulator();
      for (CandleAccumulator acc : accumulators) {
        if (Double.isNaN(merged.open)) {
          // For the first non-empty accumulator, copy its values.
          merged.open = acc.open;
          merged.high = acc.high;
          merged.low = acc.low;
          merged.close = acc.close;
          merged.volume = acc.volume;
          merged.openTimestamp = acc.openTimestamp;
          merged.currencyPair = acc.currencyPair;
        } else {
          // Use the earliest open timestamp for the open price.
          long mergedOpenMillis = Timestamps.toMillis(merged.openTimestamp);
          long accOpenMillis = Timestamps.toMillis(acc.openTimestamp);
          if (accOpenMillis < mergedOpenMillis) {
            merged.open = acc.open;
            merged.openTimestamp = acc.openTimestamp;
          }
          // For the close price, choose the accumulator with the later openTimestamp.
          if (accOpenMillis > mergedOpenMillis) {
            merged.close = acc.close;
          }
          merged.high = Math.max(merged.high, acc.high);
          merged.low = Math.min(merged.low, acc.low);
          merged.volume += acc.volume;
        }
      }
      return merged;
    }

    @Override
    public Candle extractOutput(CandleAccumulator accumulator) {
      Candle.Builder builder = Candle.newBuilder();
      builder.setTimestamp(accumulator.openTimestamp);
      builder.setCurrencyPair(accumulator.currencyPair);
      builder.setOpen(accumulator.open);
      builder.setHigh(accumulator.high);
      builder.setLow(accumulator.low);
      builder.setClose(accumulator.close);
      builder.setVolume(accumulator.volume);
      return builder.build();
    }
  }

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Trade>> input) {
    // 1. Apply sliding windowing to segment the stream into overlapping windows.
    PCollection<KV<String, Trade>> windowedTrades = input.apply("ApplySlidingWindow",
        Window.<KV<String, Trade>>into(
            SlidingWindows.of(windowDuration).every(slidePeriod))
            .withAllowedLateness(allowedLateness)
            .discardingFiredPanes());

    // 2. Aggregate trades per key within each window into a Candle.
    PCollection<KV<String, Candle>> candlePerWindow = windowedTrades.apply("AggregateToCandle",
        Combine.perKey(new CandleCombineFn()));

    // 3. Group all windowed candles per key.
    // Note: In a streaming scenario with sliding windows, each key may appear in multiple windows.
    PCollection<KV<String, Iterable<Candle>>> groupedCandles =
        candlePerWindow.apply("GroupCandles", GroupByKey.create());

    // 4. Convert the Iterable<Candle> into an ImmutableList<Candle> for each key.
    PCollection<KV<String, ImmutableList<Candle>>> output = groupedCandles.apply("ToImmutableList",
        MapElements.into(TypeDescriptors.kvs(
            TypeDescriptors.strings(),
            TypeDescriptors.lists(TypeDescriptors.of(Candle.class))
        )).via(kv -> KV.of(kv.getKey(), ImmutableList.copyOf(kv.getValue()))));

    return output;
  }
}
