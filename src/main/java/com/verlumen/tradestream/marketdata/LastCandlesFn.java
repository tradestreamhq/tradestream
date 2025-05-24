package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.apache.beam.sdk.coders.ListCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.values.KV;

/**
 * LastCandlesFn buffers and outputs the last N candles per key. It also replaces a default (dummy)
 * candle with a filled candle using the last real candle’s close. Additionally, it avoids buffering
 * duplicate default candles.
 */
public class LastCandlesFn {
  private static final double ZERO = 0.0;

  public static class BufferLastCandles
      extends DoFn<KV<String, Candle>, KV<String, ImmutableList<Candle>>> {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final int maxCandles;

    public BufferLastCandles(int maxCandles) {
      this.maxCandles = maxCandles;
    }

    @StateId("candleBuffer")
    private final StateSpec<ValueState<List<Candle>>> bufferSpec =
        StateSpecs.value(ListCoder.of(ProtoCoder.of(Candle.class)));

    @ProcessElement
    public void processElement(
        ProcessContext context,
        @Element KV<String, Candle> element,
        @StateId("candleBuffer") ValueState<List<Candle>> bufferState) {

      String key = element.getKey();
      Candle incoming = element.getValue();

      logger.atFine().log("Processing element for key: %s with incoming candle: %s", key, incoming);

      // Read the current buffer state.
      List<Candle> buffer = bufferState.read();
      if (buffer == null) {
        logger.atFine().log("Buffer for key: %s is null. Initializing a new buffer.", key);
        buffer = new ArrayList<>();
      } else {
        logger.atFine().log(
            "Current buffer size for key: %s is %d. Buffer content: %s",
            key, buffer.size(), buffer);
      }

      // Check if the incoming candle is default (all zeros).
      if (isDefaultCandle(incoming)) {
        logger.atFine().log("Incoming candle for key: %s is a default candle.", key);

        // If we have a default candle at the end of the buffer already, skip adding this duplicate.
        if (!buffer.isEmpty()) {
          Candle lastCandle = buffer.get(buffer.size() - 1);
          if (isDefaultCandle(lastCandle)) {
            logger.atFine().log(
                "Detected duplicate default candle for key: %s. Skipping addition. Buffer remains"
                    + " unchanged.",
                key);
            // Emit the current buffer without changes.
            context.output(KV.of(key, ImmutableList.copyOf(buffer)));
            return;
          }
        }

        // If it's a default candle but there is at least one candle in the buffer,
        // replace with a 'filled' candle using the last real candle's close.
        if (!buffer.isEmpty()) {
          Candle lastReal = buffer.get(buffer.size() - 1);
          incoming =
              Candle.newBuilder()
                  .setOpen(lastReal.getClose())
                  .setHigh(lastReal.getClose())
                  .setLow(lastReal.getClose())
                  .setClose(lastReal.getClose())
                  .setVolume(ZERO)
                  .setTimestamp(incoming.getTimestamp()) // Keep the synthetic candle's timestamp
                  .setCurrencyPair(incoming.getCurrencyPair())
                  .build();
          logger.atFine().log(
              "Replacing default candle with filled candle based on last real candle's close for"
                  + " key: %s",
              key);
        }
      }

      // Add the incoming (or replaced) candle to the buffer.
      buffer.add(incoming);
      logger.atFine().log(
          "Added new candle to the buffer for key: %s. Buffer size is now %d.", key, buffer.size());

      // Enforce the maximum buffer size.
      while (buffer.size() > maxCandles) {
        Candle removed = buffer.remove(0);
        logger.atFine().log(
            "Buffer size exceeded max (%d). Removing oldest candle: %s for key: %s",
            maxCandles, removed, key);
      }

      // (Optional) sort the buffer by timestamp ascending.
      buffer.sort(Comparator.comparingLong(c -> c.getTimestamp().getSeconds()));
      logger.atFine().log(
          "Sorted the buffer by timestamp for key: %s. Current buffer: %s", key, buffer);

      // Write back the updated buffer.
      bufferState.write(buffer);
      logger.atFine().log("Updated state for key: %s with buffer size %d", key, buffer.size());

      // Output the current buffer as an immutable list.
      context.output(KV.of(key, ImmutableList.copyOf(buffer)));
      logger.atFine().log("Emitted buffer for key: %s -> %s", key, buffer);
    }

    private boolean isDefaultCandle(Candle candle) {
      return candle.getOpen() == ZERO
          && candle.getHigh() == ZERO
          && candle.getLow() == ZERO
          && candle.getClose() == ZERO
          && candle.getVolume() == ZERO;
    }
  }
}
