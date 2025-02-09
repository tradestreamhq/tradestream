package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
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
 * LastCandlesFn buffers and outputs the last N candles per key.
 * It also replaces a default (dummy) candle with a filled candle using the last real candle’s close.
 * Additionally, it avoids buffering duplicate default candles.
 */
public class LastCandlesFn {
    private static final double ZERO = 0.0;

    public static class BufferLastCandles extends DoFn<KV<String, Candle>, KV<String, ImmutableList<Candle>>> {
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

            // Read the current buffer state.
            List<Candle> buffer = bufferState.read();
            if (buffer == null) {
                buffer = new ArrayList<>();
            }

            Candle incoming = element.getValue();
            String key = element.getKey();

            // If the incoming candle is default (i.e. all zeros) and there is already a default candle
            // at the end of the buffer, skip adding this duplicate.
            if (isDefaultCandle(incoming) && !buffer.isEmpty()) {
                Candle lastCandle = buffer.get(buffer.size() - 1);
                if (isDefaultCandle(lastCandle)) {
                    context.output(KV.of(key, ImmutableList.copyOf(buffer)));
                    return;
                }
            }
            
            // If the incoming candle is default and there is at least one candle in the buffer,
            // replace it with a "filled" candle using the last real candle's close.
            if (isDefaultCandle(incoming) && !buffer.isEmpty()) {
                Candle lastReal = buffer.get(buffer.size() - 1);
                incoming = Candle.newBuilder()
                        .setOpen(lastReal.getClose())
                        .setHigh(lastReal.getClose())
                        .setLow(lastReal.getClose())
                        .setClose(lastReal.getClose())
                        .setVolume(ZERO)
                        .setTimestamp(incoming.getTimestamp())  // Preserve the synthetic candle's timestamp.
                        .setCurrencyPair(incoming.getCurrencyPair())
                        .build();
            }

            // Add the incoming (or modified) candle.
            buffer.add(incoming);

            // Enforce the maximum buffer size.
            while (buffer.size() > maxCandles) {
                buffer.remove(0);
            }

            // Optionally, sort the buffer by timestamp (ascending).
            buffer.sort(Comparator.comparingLong(c -> c.getTimestamp().getSeconds()));

            // Write back the updated buffer.
            bufferState.write(buffer);

            // Output the current buffer as an immutable list.
            context.output(KV.of(key, ImmutableList.copyOf(buffer)));
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
