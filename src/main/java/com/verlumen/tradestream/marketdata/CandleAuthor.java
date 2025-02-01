package com.verlumen.tradestream.marketdata;

import com.google.protobuf.util.Timestamps;
import java.time.Instant;
import java.time.ZoneOffset;
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

public class CandleAuthor
    extends PTransform<PCollection<KV<String, Trade>>, PCollection<Candle>> {
  public static CandleAuthor create() {
    return new CandleAuthor();
  }

  @Override
  public PCollection<Candle> expand(PCollection<KV<String, Trade>> input) {
    // Note: Make sure the input is windowed. For example:
    //   input.apply(Window.into(FixedWindows.of(windowDuration))
    //         .withAllowedLateness(allowedLateness)
    //         .triggering(DefaultTrigger.of())
    //         .discardingFiredPanes());
    
    return input.apply("AggregateToCandle", ParDo.of(new DoFn<KV<String, Trade>, Candle>() {
      
      // State to hold the aggregate (for the current window)
      @StateId("aggState")
      private final StateSpec<ValueState<Aggregate>> aggStateSpec = StateSpecs.value();

      // State to hold the previous candle across windows
      @StateId("prevCandle")
      private final StateSpec<ValueState<Candle>> prevCandleSpec = StateSpecs.value();

      // A timer to fire at the end of the window
      @TimerId("windowTimer")
      private final TimerSpec timerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME);

      @ProcessElement
      public void processElement(
          ProcessContext c,
          @StateId("aggState") ValueState<Aggregate> aggState,
          @TimerId("windowTimer") Timer timer,
          BoundedWindow window) {

        // Set a timer to fire at the end of this window
        // (for an IntervalWindow, window.maxTimestamp() is the end)
        timer.set(window.maxTimestamp());
        
        // Update the aggregator with the current trade
        KV<String, Trade> element = c.element();
        Trade trade = element.getValue();
        Aggregate currentAgg = aggState.read();
        if (currentAgg == null) {
          // For the first trade in the window, initialize the aggregate.
          currentAgg = new Aggregate(trade.getPrice(), trade.getPrice(), trade.getPrice(), trade.getPrice(), trade.getVolume());
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
          @StateId("prevCandle") ValueState<Candle> prevCandleState) {
        
        // Determine the window start (use the window's start time as the candle timestamp)
        IntervalWindow window = (IntervalWindow) c.window();
        long windowStartMillis = window.start().getMillis();
        
        Candle outputCandle;
        Aggregate agg = aggState.read();
        if (agg != null) {
          // If there were trades, build the candle from the aggregated values.
          outputCandle = Candle.newBuilder()
              .setCurrencyPair(c.getKey())
              .setTimestamp(Timestamps.fromMillis(windowStartMillis))
              .setOpen(agg.open)
              .setHigh(agg.high)
              .setLow(agg.low)
              .setClose(agg.close)
              .setVolume(agg.volume)
              .build();
        } else {
          // If no trades occurred, try to mirror the previous candle.
          Candle prev = prevCandleState.read();
          if (prev != null) {
            outputCandle = Candle.newBuilder()
                .setCurrencyPair(prev.getCurrencyPair())
                .setTimestamp(Timestamps.fromMillis(windowStartMillis))
                .setOpen(prev.getOpen())
                .setHigh(prev.getHigh())
                .setLow(prev.getLow())
                .setClose(prev.getClose())
                .setVolume(0)
                .build();
          } else {
            // If no previous candle exists (e.g. at pipeline startup), do not output a candle.
            return;
          }
        }
        // Emit the candle.
        c.output(outputCandle);
        // Save it as the previous candle for the key.
        prevCandleState.write(outputCandle);
        // Clear the aggregator state for the next window.
        aggState.clear();
      }

      // A simple POJO to accumulate values.
      private static class Aggregate {
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
