package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.SerializableFunction;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.junit.Rule;
import org.junit.Test;

public class LastCandlesFnTest {
    private static final double DELTA = 1e-6;
    private static final double ZERO = 0.0;

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    /**
     * Helper method that picks the output with the largest buffered list,
     * which we assume to be the final state.
     */
    private static KV<String, ImmutableList<Candle>> pickFinalState(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
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
        // Arrange
        final Candle candle1 = Candle.newBuilder()
                .setOpen(100)
                .setHigh(110)
                .setLow(90)
                .setClose(105)
                .setVolume(1)
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new LastCandlesFn.BufferLastCandles(3)))
        ).satisfies(new SerializableFunction<Iterable<KV<String, ImmutableList<Candle>>>, Void>() {
            @Override
            public Void apply(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
                KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
                assertEquals("BTC/USD", finalKv.getKey());
                assertEquals(1, finalKv.getValue().size());
                assertEquals(candle1, finalKv.getValue().get(0));
                return null;
            }
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferDefaultCandleReplacement() {
        // Arrange: Create a real candle and a default (synthetic) candle.
        final Candle realCandle = Candle.newBuilder()
                .setOpen(105)
                .setHigh(115)
                .setLow(95)
                .setClose(110)
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        final Candle defaultCandle = Candle.newBuilder()
                .setOpen(ZERO)
                .setHigh(ZERO)
                .setLow(ZERO)
                .setClose(ZERO)
                .setVolume(ZERO)
                .setTimestamp(Timestamp.getDefaultInstance())
                .setCurrencyPair(realCandle.getCurrencyPair())
                .build();

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", realCandle), KV.of("BTC/USD", defaultCandle)))
                    .apply(ParDo.of(new LastCandlesFn.BufferLastCandles(3)))
        ).satisfies(new SerializableFunction<Iterable<KV<String, ImmutableList<Candle>>>, Void>() {
            @Override
            public Void apply(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
                KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
                assertEquals("BTC/USD", finalKv.getKey());
                ImmutableList<Candle> buffer = finalKv.getValue();
                // Expect two candles: one for the filled default and one for the real candle.
                assertEquals(2, buffer.size());
                // Because the DoFn sorts by timestamp (ascending) and the filled candle uses the
                // default candle’s timestamp (0), it appears first.
                Candle filledCandle = buffer.get(0);
                Candle bufferedRealCandle = buffer.get(1);
                // The filled candle should have all prices equal to the real candle’s close (110)
                // and volume zero.
                assertEquals(realCandle.getClose(), filledCandle.getOpen(), DELTA);
                assertEquals(realCandle.getClose(), filledCandle.getHigh(), DELTA);
                assertEquals(realCandle.getClose(), filledCandle.getLow(), DELTA);
                assertEquals(realCandle.getClose(), filledCandle.getClose(), DELTA);
                assertEquals(ZERO, filledCandle.getVolume(), DELTA);
                // The real candle should remain unchanged.
                assertEquals(realCandle, bufferedRealCandle);
                return null;
            }
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferExceedsLimitEviction() {
        // Arrange: Create four candles with increasing timestamps.
        final Candle candle1 = Candle.newBuilder()
                .setOpen(100)
                .setHigh(110)
                .setLow(90)
                .setClose(105)
                .setVolume(1)
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        final Candle candle2 = Candle.newBuilder()
                .setOpen(105)
                .setHigh(115)
                .setLow(95)
                .setClose(110)
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        final Candle candle3 = Candle.newBuilder()
                .setOpen(110)
                .setHigh(120)
                .setLow(100)
                .setClose(115)
                .setVolume(1.5)
                .setTimestamp(Timestamp.newBuilder().setSeconds(3000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        final Candle candle4 = Candle.newBuilder()
                .setOpen(115)
                .setHigh(125)
                .setLow(105)
                .setClose(120)
                .setVolume(1.8)
                .setTimestamp(Timestamp.newBuilder().setSeconds(4000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        // Act & Assert:
        // With a maximum buffer size of 3, after processing four candles the oldest (candle1)
        // should be evicted. The final sorted state should be [candle2, candle3, candle4].
        PAssert.that(
            pipeline.apply(Create.of(
                        KV.of("BTC/USD", candle1),
                        KV.of("BTC/USD", candle2),
                        KV.of("BTC/USD", candle3),
                        KV.of("BTC/USD", candle4)))
                    .apply(ParDo.of(new LastCandlesFn.BufferLastCandles(3)))
        ).satisfies(new SerializableFunction<Iterable<KV<String, ImmutableList<Candle>>>, Void>() {
            @Override
            public Void apply(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
                KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
                assertEquals("BTC/USD", finalKv.getKey());
                ImmutableList<Candle> buffer = finalKv.getValue();
                assertEquals(3, buffer.size());
                // Because the buffer is sorted by timestamp, the expected order is:
                // candle2 (timestamp 2000), candle3 (timestamp 3000), candle4 (timestamp 4000).
                assertEquals(candle2, buffer.get(0));
                assertEquals(candle3, buffer.get(1));
                assertEquals(candle4, buffer.get(2));
                return null;
            }
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
                    .apply(ParDo.of(new LastCandlesFn.BufferLastCandles(3)))
        ).satisfies(new SerializableFunction<Iterable<KV<String, ImmutableList<Candle>>>, Void>() {
            @Override
            public Void apply(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
                assertTrue(!outputs.iterator().hasNext());
                return null;
            }
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferZeroSize() {
        // Arrange: With a maximum buffer size of zero, the final state should be empty.
        final Candle candle1 = Candle.newBuilder()
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
                    .apply(ParDo.of(new LastCandlesFn.BufferLastCandles(0)))
        ).satisfies(new SerializableFunction<Iterable<KV<String, ImmutableList<Candle>>>, Void>() {
            @Override
            public Void apply(Iterable<KV<String, ImmutableList<Candle>>> outputs) {
                KV<String, ImmutableList<Candle>> finalKv = pickFinalState(outputs);
                assertEquals("BTC/USD", finalKv.getKey());
                assertTrue(finalKv.getValue().isEmpty());
                return null;
            }
        });
        pipeline.run().waitUntilFinish();
    }
}
