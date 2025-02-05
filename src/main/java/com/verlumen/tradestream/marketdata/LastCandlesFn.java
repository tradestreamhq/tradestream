package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
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
        public void processElement(@Element KV<String, Candle> element,
                                 @StateId("candleBuffer") ValueState<LinkedList<Candle>> bufferState,
                                 OutputReceiver<KV<String, ImmutableList<Candle>>> out) {
            LinkedList<Candle> buffer = bufferState.read();
            if (buffer == null) {
                buffer = new LinkedList<>();
            }
            Candle incoming = element.getValue();
            
            if (isDefaultCandle(incoming) && !buffer.isEmpty()) {
                Candle lastReal = buffer.peekLast();
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
            buffer.addLast(incoming);
            while (buffer.size() > maxCandles) {
                buffer.removeFirst();
            }
            bufferState.write(buffer);

            ArrayList<Candle> sorted = new ArrayList<>(buffer);
            sorted.sort((c1, c2) -> Long.compare(
                c1.getTimestamp().getSeconds(),
                c2.getTimestamp().getSeconds()
            ));
            out.output(KV.of(element.getKey(), ImmutableList.copyOf(sorted)));
        }

        private boolean isDefaultCandle(Candle candle) {
            return Candle.getDefaultInstance().equals(candle);
        }
    }
}
