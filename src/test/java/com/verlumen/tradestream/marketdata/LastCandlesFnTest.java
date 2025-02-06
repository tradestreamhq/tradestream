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
import org.joda.time.Instant;
import org.junit.Rule;
import org.junit.Test;
import java.util.LinkedList;

public class LastCandlesFnTest {
    private static final double DELTA = 1e-6;
    private static final double ZERO = 0.0;

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testBufferSingleCandle() {
        // Arrange
        Candle candle1 = Candle.newBuilder()
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
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            KV<String, ImmutableList<Candle>> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            assertEquals(1, kv.getValue().size());
            assertEquals(candle1, kv.getValue().get(0));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferDefaultCandleReplacement() {
        // Arrange: First, add a real candle, then add a default (dummy) candle.
        Candle realCandle = Candle.newBuilder()
                .setOpen(105)
                .setHigh(115)
                .setLow(95)
                .setClose(110)
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        // Create a default candle (no trades)
        Candle defaultCandle = Candle.newBuilder()
                .setOpen(ZERO)
                .setHigh(ZERO)
                .setLow(ZERO)
                .setClose(ZERO)
                .setVolume(ZERO)
                .setTimestamp(Timestamp.getDefaultInstance())
                .setCurrencyPair(realCandle.getCurrencyPair())
                .build();

        // Act & Assert: When a default candle is added after a real one, it should be replaced.
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", realCandle), KV.of("BTC/USD", defaultCandle)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            KV<String, ImmutableList<Candle>> kv = iterable.iterator().next();
            // The buffer should contain two candles: realCandle and then the dummy candle based on realCandle's close.
            assertEquals("BTC/USD", kv.getKey());
            ImmutableList<Candle> list = kv.getValue();
            assertEquals(2, list.size());
            Candle filledCandle = list.get(1);
            // Expect open/high/low/close equal to realCandle.getClose() and volume zero.
            assertEquals(realCandle.getClose(), filledCandle.getOpen(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getHigh(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getLow(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getClose(), DELTA);
            assertEquals(ZERO, filledCandle.getVolume(), DELTA);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferExceedsLimitEviction() {
        // Arrange
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

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(
                        KV.of("BTC/USD", candle1),
                        KV.of("BTC/USD", candle2),
                        KV.of("BTC/USD", candle3),
                        KV.of("BTC/USD", candle4)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            KV<String, ImmutableList<Candle>> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            assertEquals(3, kv.getValue().size());
            // Expected eviction: candle1 is evicted; remaining: candle2, candle3, candle4.
            assertEquals(candle2, kv.getValue().get(0));
            assertEquals(candle3, kv.getValue().get(1));
            assertEquals(candle4, kv.getValue().get(2));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferEmptyInput() {
        // Arrange & Act & Assert: When input is empty, no output should be produced.
        PAssert.that(
            pipeline.apply(Create.empty(org.apache.beam.sdk.coders.KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle.class))))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            assertTrue(!iterable.iterator().hasNext());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferZeroSize() {
        // Arrange
        Candle candle1 = Candle.newBuilder()
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
                    .apply(ParDo.of(new BufferLastCandles(0)))
        ).satisfies(iterable -> {
            KV<String, ImmutableList<Candle>> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            assertTrue(kv.getValue().isEmpty());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }
}
