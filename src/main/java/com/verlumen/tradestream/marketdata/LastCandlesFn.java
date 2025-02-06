package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.LinkedList;
import org.apache.beam.sdk.coders.ListCoder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.values.KV;

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

            // Read current buffer state
            List<Candle> buffer = bufferState.read();
            if (buffer == null) {
                buffer = new ArrayList<>();
            }

            Candle incoming = element.getValue();
            String key = element.getKey();

            // Handle default candle case
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

            // Add new candle and maintain size limit
            buffer.add(incoming);
            while (buffer.size() > maxCandles) {
                buffer.remove(0);
            }

            // Sort by timestamp
            buffer.sort(Comparator.comparingLong(c -> c.getTimestamp().getSeconds()));
            
            // Write back to state
            bufferState.write(buffer);

            // Output the current buffer
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
