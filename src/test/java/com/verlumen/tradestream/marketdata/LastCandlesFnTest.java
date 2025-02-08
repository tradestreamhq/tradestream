package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.LastCandlesFn.BufferLastCandles;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.junit.Rule;
import org.junit.Test;

public class LastCandlesFnTest {
    private static final double DELTA = 1e-6;
    private static final double ZERO = 0.0;

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    /**
     * Utility method that picks the output KV for a given key with the largest buffered list.
     * (Since the stateful DoFn emits multiple outputs, the one with the largest buffer
     * is most likely the final state.)
     */
    private KV<String, ImmutableList<Candle>> pickFinalState(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
        ImmutableList<KV<String, ImmutableList<Candle>>> list = ImmutableList.copyOf(outputs);
        KV<String, ImmutableList<Candle>> finalKv = null;
        for (KV<String, ImmutableList<Candle>> kv : list) {
            if (finalKv == null || kv.getValue().size() > finalKv.getValue().size()) {
                finalKv = kv;
            }
        }
        return finalKv;
    }

    @Test
    public void testBufferSingleCandle() {
        // Arrange: create one candle.
        Candle candle1 = Candle.newBuilder()
                .setOpen(100)
                .setHigh(110)
                .setLow(90)
                .setClose(105)
                .setVolume(1)
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        // Act & Assert: Expect the final state to contain that one candle.
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(outputs -> {
            KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
            assertEquals("BTC/USD", finalKv.getKey());
            assertEquals(1, finalKv.getValue().size());
            assertEquals(candle1, finalKv.getValue().get(0));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferDefaultCandleReplacement() {
        // Arrange:
        // Create a "real" candle.
        Candle realCandle = Candle.newBuilder()
                .setOpen(105)         // real candle's open (unchanged)
                .setHigh(115)
                .setLow(95)
                .setClose(110)        // real candle's close (to be used for replacement)
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        // Create a default (synthetic) candle with all zeros and a default timestamp.
        Candle defaultCandle = Candle.newBuilder()
                .setOpen(ZERO)
                .setHigh(ZERO)
                .setLow(ZERO)
                .setClose(ZERO)
                .setVolume(ZERO)
                .setTimestamp(Timestamp.getDefaultInstance())  // timestamp = 0
                .setCurrencyPair(realCandle.getCurrencyPair())
                .build();

        // Act & Assert:
        // When processing a real candle then a default candle,
        // the default candle should be replaced with a filled candle whose
        // open/high/low/close are set to the real candle's close (110)
        // and whose volume remains zero.
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", realCandle), KV.of("BTC/USD", defaultCandle)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(outputs -> {
            KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
            assertEquals("BTC/USD", finalKv.getKey());
            ImmutableList<Candle> buffer = finalKv.getValue();
            // We expect two candles in the final state.
            assertEquals(2, buffer.size());
            // Because the DoFn sorts the buffer by timestamp (ascending), and the filled
            // candle uses the default candle’s timestamp (which is 0) while the real candle
            // has timestamp 2000, the filled candle will appear first.
            Candle filledCandle = buffer.get(0);
            Candle bufferedRealCandle = buffer.get(1);
            // The filled candle should have its open/high/low/close set to realCandle.getClose() (i.e. 110)
            assertEquals(realCandle.getClose(), filledCandle.getOpen(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getHigh(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getLow(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getClose(), DELTA);
            // And its volume should be zero.
            assertEquals(ZERO, filledCandle.getVolume(), DELTA);
            // The real candle should remain unchanged.
            assertEquals(realCandle, bufferedRealCandle);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferExceedsLimitEviction() {
        // Arrange: Create four candles with increasing timestamps.
        Candle candle1 = Candle.newBuilder()
                .setOpen(100)
                .setHigh(110)
                .setLow(90)
                .setClose(105)
                .setVolume(1)
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        Candle candle2 = Candle.newBuilder()
                .setOpen(105)
                .setHigh(115)
                .setLow(95)
                .setClose(110)
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        Candle candle3 = Candle.newBuilder()
                .setOpen(110)
                .setHigh(120)
                .setLow(100)
                .setClose(115)
                .setVolume(1.5)
                .setTimestamp(Timestamp.newBuilder().setSeconds(3000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        Candle candle4 = Candle.newBuilder()
                .setOpen(115)
                .setHigh(125)
                .setLow(105)
                .setClose(120)
                .setVolume(1.8)
                .setTimestamp(Timestamp.newBuilder().setSeconds(4000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        // Act & Assert:
        // With a maximum buffer size of 3, after processing 4 candles the oldest (candle1)
        // should be evicted. The final sorted buffer should be [candle2, candle3, candle4].
        PAssert.that(
            pipeline.apply(Create.of(
                        KV.of("BTC/USD", candle1),
                        KV.of("BTC/USD", candle2),
                        KV.of("BTC/USD", candle3),
                        KV.of("BTC/USD", candle4)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(outputs -> {
            KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
            assertEquals("BTC/USD", finalKv.getKey());
            ImmutableList<Candle> buffer = finalKv.getValue();
            assertEquals(3, buffer.size());
            // Because the buffer is sorted by timestamp, the remaining candles should be in order:
            // candle2 (timestamp 2000), candle3 (timestamp 3000), candle4 (timestamp 4000).
            assertEquals(candle2, buffer.get(0));
            assertEquals(candle3, buffer.get(1));
            assertEquals(candle4, buffer.get(2));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferEmptyInput() {
        // Arrange & Act & Assert: With empty input, no output should be produced.
        PAssert.that(
            pipeline.apply(Create.empty(
                    org.apache.beam.sdk.coders.KvCoder.of(
                            StringUtf8Coder.of(), ProtoCoder.of(Candle.class))))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(outputs -> {
            assertTrue(!outputs.iterator().hasNext());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferZeroSize() {
        // Arrange: With a maximum buffer size of zero, the final state should be empty.
        Candle candle1 = Candle.newBuilder()
                .setOpen(100)
                .setHigh(110)
                .setLow(90)
                .setClose(105)
                .setVolume(1)
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        // Act & Assert:
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new BufferLastCandles(0)))
        ).satisfies(outputs -> {
            KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
            assertEquals("BTC/USD", finalKv.getKey());
            assertTrue(finalKv.getValue().isEmpty());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }
}
