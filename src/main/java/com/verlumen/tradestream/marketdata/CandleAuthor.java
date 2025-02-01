package com.verlumen.tradestream.marketdata;

import com.google.protobuf.util.Timestamps;
import java.io.Serializable;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.state.Timer;
import org.apache.beam.sdk.state.TimerSpecs;
import org.apache.beam.sdk.state.TimeDomain;
import org.apache.beam.sdk.state.TimerSpec;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.StateId;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.windowing.BoundedWindow;
import org.apache.beam.sdk.transforms.windowing.IntervalWindow;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Duration;

public class CreateCandles extends PTransform<PCollection<KV<String, Trade>>, PCollection<Candle>> {
  public static CreateCandles create() {
    return new CreateCandles();
  }

  @Override
  public PCollection<Candle> expand(PCollection<KV<String, Trade>> input) {
    // Note: Make sure the input is windowed. For example:
    //   input.apply(Window.into(FixedWindows.of(windowDuration))
    //         .withAllowedLateness(allowedLateness)
    //         .triggering(DefaultTrigger.of())
    //         .discardingFiredPanes());

    return input.apply(
        "AggregateToCandle",
        ParDo.of(
            new DoFn<KV<String, Trade>, Candle>() {

              // State to hold the aggregate (for the current window)
              @StateId("aggState")
              private final StateSpec<ValueState<Aggregate>> aggStateSpec =
                  StateSpecs.value(SerializableCoder.of(Aggregate.class));

              @StateId("keyState")
              private final StateSpec<ValueState<String>> keyStateSpec =
                  StateSpecs.value(StringUtf8Coder.of());

              // State to hold the previous candle across windows
              @StateId("prevCandle")
              private final StateSpec<ValueState<Candle>> prevCandleSpec =
                  StateSpecs.value(ProtoCoder.of(Candle.class));

              // A timer to fire at the end of the window
              @TimerId("windowTimer")
              private final TimerSpec timerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME);

              @ProcessElement
              public void processElement(
                  ProcessContext c,
                  @StateId("aggState") ValueState<Aggregate> aggState,
                  @StateId("keyState") ValueState<String> keyState,
                  @TimerId("windowTimer") Timer timer,
                  BoundedWindow window) {

                // Set the timer as before.
                timer.set(window.maxTimestamp());

                // Save the key if it hasn't been saved already.
                if (keyState.read() == null) {
                  keyState.write(c.element().getKey());
                }

                // Update your aggregate with the current trade.
                Trade trade = c.element().getValue();
                Aggregate currentAgg = aggState.read();
                if (currentAgg == null) {
                  currentAgg =
                      new Aggregate(
                          trade.getPrice(),
                          trade.getPrice(),
                          trade.getPrice(),
                          trade.getPrice(),
                          trade.getVolume());
                } else {
                  currentAgg.high = Math.max(currentAgg.high, trade.getPrice());
                  currentAgg.low = Math.min(currentAgg.low, trade.getPrice());
                  currentAgg.close = trade.getPrice();
                  currentAgg.volume += trade.getVolume();
                }
                aggState.write(currentAgg);
              }

              @OnTimer("windowTimer")
              public void onTimer(
                  OnTimerContext c,
                  @StateId("aggState") ValueState<Aggregate> aggState,
                  @StateId("prevCandle") ValueState<Candle> prevCandleState,
                  @StateId("keyState") ValueState<String> keyState) {

                IntervalWindow window = (IntervalWindow) c.window();
                long windowStartMillis = window.start().getMillis();

                String key = keyState.read();
                Candle outputCandle;
                Aggregate agg = aggState.read();
                if (agg != null) {
                  outputCandle =
                      Candle.newBuilder()
                          .setCurrencyPair(key)
                          .setTimestamp(Timestamps.fromMillis(windowStartMillis))
                          .setOpen(agg.open)
                          .setHigh(agg.high)
                          .setLow(agg.low)
                          .setClose(agg.close)
                          .setVolume(agg.volume)
                          .build();
                } else {
                  Candle prev = prevCandleState.read();
                  if (prev != null) {
                    outputCandle =
                        Candle.newBuilder()
                            .setCurrencyPair(prev.getCurrencyPair())
                            .setTimestamp(Timestamps.fromMillis(windowStartMillis))
                            .setOpen(prev.getOpen())
                            .setHigh(prev.getHigh())
                            .setLow(prev.getLow())
                            .setClose(prev.getClose())
                            .setVolume(0)
                            .build();
                  } else {
                    return; // No candle to output.
                  }
                }
                c.output(outputCandle);
                prevCandleState.write(outputCandle);
                aggState.clear();
              }

              // A simple POJO to accumulate values.
              private static class Aggregate implements Serializable {
                double open;
                double high;
                double low;
                double close;
                double volume;

                Aggregate(double open, double high, double low, double close, double volume) {
                  this.open = open;
                  this.high = high;
                  this.low = low;
                  this.close = close;
                  this.volume = volume;
                }
              }
            }));
  }
}
