package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.apache.beam.sdk.coders.ListCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.state.StateId;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.Element;
import org.apache.beam.sdk.transforms.DoFn.Key;
import org.apache.beam.sdk.transforms.DoFn.OnTimer;
import org.apache.beam.sdk.transforms.DoFn.ProcessElement;
import org.apache.beam.sdk.transforms.DoFn.TimerId;
import org.apache.beam.sdk.transforms.TimerSpec;
import org.apache.beam.sdk.transforms.TimerSpecs;
import org.apache.beam.sdk.transforms.DoFn.OnTimerContext;
import org.apache.beam.sdk.transforms.DoFn.ProcessContext;
import org.apache.beam.sdk.transforms.windowing.GlobalWindow;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Duration;
import org.joda.time.Instant;

public class LastCandlesFn {
  private static final double ZERO = 0.0;

  /**
   * This stateful DoFn buffers incoming candles (per key) and emits the final sorted list
   * after no new element has been seen for a configurable delay.
   *
   * In production you may use event‑time timers when using windowing. Here we use a processing‑time timer
   * for simplicity.
   */
  public static class BufferLastCandles extends DoFn<KV<String, Candle>, KV<String, ImmutableList<Candle>>> {
    private final int maxCandles;
    private final Duration flushDelay;  // Flush state if no new element arrives within this delay.

    public BufferLastCandles(int maxCandles, Duration flushDelay) {
      this.maxCandles = maxCandles;
      this.flushDelay = flushDelay;
    }

    // Define the state to buffer the candles for each key.
    @StateId("candleBuffer")
    private final StateSpec<ValueState<List<Candle>>> bufferSpec =
        StateSpecs.value(ListCoder.of(ProtoCoder.of(Candle.class)));

    // Define a processing-time timer.
    @TimerId("flushTimer")
    private final TimerSpec flushTimerSpec = TimerSpecs.timer(org.apache.beam.sdk.state.TimeDomain.PROCESSING_TIME);

    /**
     * For each incoming element (which is already keyed), update the state.
     * Also schedule a flush timer flushDelay into the future.
     */
    @ProcessElement
    public void processElement(
        @Element KV<String, Candle> element,
        @Key String key,
        @StateId("candleBuffer") ValueState<List<Candle>> bufferState,
        @TimerId("flushTimer") org.apache.beam.sdk.state.Timer flushTimer,
        ProcessContext context) {

      // Read existing state (or initialize if empty).
      List<Candle> buffer = bufferState.read();
      if (buffer == null) {
        buffer = new ArrayList<>();
      }
      
      // Process the incoming candle.
      Candle incoming = element.getValue();
      if (isDefaultCandle(incoming) && !buffer.isEmpty()) {
        Candle lastReal = buffer.get(buffer.size() - 1);
        incoming = Candle.newBuilder()
            .setOpen(lastReal.getClose())
            .setHigh(lastReal.getClose())
            .setLow(lastReal.getClose())
            .setClose(lastReal.getClose())
            .setVolume(ZERO)
            .setTimestamp(incoming.getTimestamp())
            .setCurrencyPair(incoming.getCurrencyPair())
            .build();
      }
      buffer.add(incoming);
      
      // Evict older candles if the buffer exceeds the allowed size.
      while (buffer.size() > maxCandles) {
        buffer.remove(0);
      }
      
      // Write the updated state.
      bufferState.write(buffer);
      
      // (Re-)schedule the flush timer to fire flushDelay from the current element's timestamp.
      flushTimer.set(context.timestamp().plus(flushDelay));
    }

    /**
     * When the flush timer fires, output the final buffered (and sorted) list of candles
     * for the key and clear the state.
     */
    @OnTimer("flushTimer")
    public void onFlush(
        OnTimerContext c,
        @Key String key,
        @StateId("candleBuffer") ValueState<List<Candle>> bufferState,
        OutputReceiver<KV<String, ImmutableList<Candle>>> out) {

      List<Candle> buffer = bufferState.read();
      if (buffer != null && !buffer.isEmpty()) {
        // Sort the buffered candles by their timestamp.
        List<Candle> sorted = new ArrayList<>(buffer);
        sorted.sort(Comparator.comparingLong(candle -> candle.getTimestamp().getSeconds()));
        
        // Emit the final state for this key.
        out.output(KV.of(key, ImmutableList.copyOf(sorted)));
      }
      // Clear the state.
      bufferState.clear();
    }

    private boolean isDefaultCandle(Candle candle) {
      return Candle.getDefaultInstance().equals(candle);
    }
  }
}
