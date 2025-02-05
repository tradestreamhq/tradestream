package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.LinkedList;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.state.StateId;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.values.KV;

/**
 * LastCandlesFn buffers and emits the last N candles per key.
 * If a synthetic (default) candle is encountered, it is replaced by a dummy candle
 * using the last real candle’s close price for open, high, low, and close, with volume set to 0.
 */
public class LastCandlesFn {

    public static class BufferLastCandles extends DoFn<KV<String, Candle>, KV<String, ImmutableList<Candle>>> {

        private final int maxCandles;

        public BufferLastCandles(int maxCandles) {
            this.maxCandles = maxCandles;
        }

        @StateId("candleBuffer")
        private final org.apache.beam.sdk.state.StateSpec<ValueState<Deque<Candle>>> bufferSpec =
                StateSpecs.value(SerializableCoder.of(new org.apache.beam.sdk.values.TypeDescriptor<Deque<Candle>>() {}));

        @ProcessElement
        public void processElement(@Element KV<String, Candle> element,
                                   @StateId("candleBuffer") ValueState<Deque<Candle>> bufferState,
                                   OutputReceiver<KV<String, ImmutableList<Candle>>> out) {
            Deque<Candle> buffer = bufferState.read();
            if (buffer == null) {
                buffer = new LinkedList<>();
            }
            Candle incoming = element.getValue();
            // If the incoming candle is a default (dummy) candle and we have a previous real candle,
            // then create a filled candle using the last real candle’s close for O/H/L/C and volume 0.
            if (isDefaultCandle(incoming) && !buffer.isEmpty()) {
                Candle lastReal = buffer.peekLast();
                incoming = Candle.newBuilder()
                        .setOpen(lastReal.getClose())
                        .setHigh(lastReal.getClose())
                        .setLow(lastReal.getClose())
                        .setClose(lastReal.getClose())
                        .setVolume(BigDecimal.ZERO)
                        .setTimestamp(incoming.getTimestamp())  // Use the synthetic candle's timestamp
                        .setCurrencyPair(incoming.getCurrencyPair())
                        .build();
            }
            buffer.addLast(incoming);
            while (buffer.size() > maxCandles) {
                buffer.removeFirst();
            }
            bufferState.write(buffer);

            ArrayList<Candle> sorted = new ArrayList<>(buffer);
            sorted.sort(Comparator.comparing(Candle::getTimestamp));
            out.output(KV.of(element.getKey(), ImmutableList.copyOf(sorted)));
        }

        private boolean isDefaultCandle(Candle candle) {
            return candle.getOpen().compareTo(BigDecimal.ZERO) == 0 &&
                   candle.getHigh().compareTo(BigDecimal.ZERO) == 0 &&
                   candle.getLow().compareTo(BigDecimal.ZERO) == 0 &&
                   candle.getClose().compareTo(BigDecimal.ZERO) == 0 &&
                   candle.getVolume().compareTo(BigDecimal.ZERO) == 0 &&
                   candle.getTimestamp().equals(com.google.protobuf.Timestamp.getDefaultInstance());
        }
    }
}
