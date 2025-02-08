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
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.junit.Rule;
import org.junit.Test;

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

        // Act & Assert: With one candle, the final buffer should contain that candle.
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            // Pick the final output (here the only one) from the stateful DoFn.
            ImmutableList<KV<String, ImmutableList<Candle>>> list = ImmutableList.copyOf(iterable);
            KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
            assertEquals("BTC/USD", kv.getKey());
            assertEquals(1, kv.getValue().size());
            assertEquals(candle1, kv.getValue().get(0));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferDefaultCandleReplacement() {
        // Arrange: First, a real candle then a default (dummy) candle.
        Candle realCandle = Candle.newBuilder()
                .setOpen(105)
                .setHigh(115)
                .setLow(95)
                .setClose(110)  // This close value should be used for replacement.
                .setVolume(1.2)
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        // Create a default candle (no trades).
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
        // When processing a real candle followed by a default candle,
        // the default candle is replaced (filled) with values based on realCandle.getClose().
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", realCandle), KV.of("BTC/USD", defaultCandle)))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            ImmutableList<KV<String, ImmutableList<Candle>>> list = ImmutableList.copyOf(iterable);
            // The final output is the one with the fully accumulated state.
            KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
            assertEquals("BTC/USD", kv.getKey());
            ImmutableList<Candle> buffer = kv.getValue();
            // We expect two candles.
            assertEquals(2, buffer.size());
            // Since sorting is by timestamp ascending, and the filled candle takes the default candle’s timestamp (0),
            // the filled (replaced) candle is at index 0, and the real candle is at index 1.
            Candle filledCandle = buffer.get(0);
            // The filled candle should have open/high/low/close equal to realCandle.getClose() (110)
            // and its volume should remain zero.
            assertEquals(realCandle.getClose(), filledCandle.getOpen(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getHigh(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getLow(), DELTA);
            assertEquals(realCandle.getClose(), filledCandle.getClose(), DELTA);
            assertEquals(ZERO, filledCandle.getVolume(), DELTA);
            // The real candle is still present as the second element.
            Candle bufferedRealCandle = buffer.get(1);
            assertEquals(realCandle, bufferedRealCandle);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    /**
     * A static DoFn to flatten grouped values. Making it static prevents capturing the outer instance.
     */
    public static class FlattenGroupedFn extends DoFn<KV<String, Iterable<Candle>>, KV<String, Candle>> {
        @ProcessElement
        public void processElement(ProcessContext c) {
            String key = c.element().getKey();
            for (Candle candle : c.element().getValue()) {
                c.output(KV.of(key, candle));
            }
        }
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
        // When processing 4 candles with maxCandles = 3, the oldest (candle1) should be evicted.
        // To ensure that all candles for a key are processed together, we group them.
        PAssert.that(
            pipeline
              .apply(Create.of(
                        KV.of("BTC/USD", candle1),
                        KV.of("BTC/USD", candle2),
                        KV.of("BTC/USD", candle3),
                        KV.of("BTC/USD", candle4)))
              // Force grouping so that state is accumulated for the key.
              .apply("GroupByKey", GroupByKey.create())
              // Flatten the grouped values back to individual KV pairs using our static DoFn.
              .apply("FlattenGrouped", ParDo.of(new FlattenGroupedFn()))
              // Now apply the stateful DoFn.
              .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            ImmutableList<KV<String, ImmutableList<Candle>>> list = ImmutableList.copyOf(iterable);
            KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
            assertEquals("BTC/USD", kv.getKey());
            ImmutableList<Candle> buffer = kv.getValue();
            // With maxCandles=3 and 4 inputs, the oldest candle (candle1) is evicted.
            assertEquals(3, buffer.size());
            // Expect the sorted order by timestamp: [candle2, candle3, candle4]
            assertEquals(candle2, buffer.get(0));
            assertEquals(candle3, buffer.get(1));
            assertEquals(candle4, buffer.get(2));
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferEmptyInput() {
        // Arrange & Act & Assert: When input is empty, no output should be produced.
        PAssert.that(
            pipeline.apply(Create.empty(
                    org.apache.beam.sdk.coders.KvCoder.of(
                            StringUtf8Coder.of(), ProtoCoder.of(Candle.class))))
                    .apply(ParDo.of(new BufferLastCandles(3)))
        ).satisfies(iterable -> {
            assertTrue(!iterable.iterator().hasNext());
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

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new BufferLastCandles(0)))
        ).satisfies(iterable -> {
            ImmutableList<KV<String, ImmutableList<Candle>>> list = ImmutableList.copyOf(iterable);
            KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
            assertEquals("BTC/USD", kv.getKey());
            assertTrue(kv.getValue().isEmpty());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }
}
