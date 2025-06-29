package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.LastCandlesFn.BufferLastCandles;
import java.util.ArrayList;
import java.util.List;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.junit.Rule;
import org.junit.Test;

public class LastCandlesFnTest {
  private static final double DELTA = 1e-6;
  private static final double ZERO = 0.0;

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  /**
   * This flattening DoFn sorts the grouped values so that any candle with nonzero open (i.e. a
   * “real” candle) comes before a default candle. This is used for the default-candle replacement
   * test.
   */
  public static class FlattenGroupedWithOrderingFn
      extends DoFn<KV<String, Iterable<Candle>>, KV<String, Candle>> {
    @ProcessElement
    public void processElement(ProcessContext c) {
      String key = c.element().getKey();
      List<Candle> list = new ArrayList<>();
      for (Candle candle : c.element().getValue()) {
        list.add(candle);
      }
      // Sort so that non-default candles (open != 0) come first.
      list.sort(
          (a, b) -> {
            boolean aDefault =
                (a.getOpen() == 0
                    && a.getHigh() == 0
                    && a.getLow() == 0
                    && a.getClose() == 0
                    && a.getVolume() == 0);
            boolean bDefault =
                (b.getOpen() == 0
                    && b.getHigh() == 0
                    && b.getLow() == 0
                    && b.getClose() == 0
                    && b.getVolume() == 0);
            if (aDefault && !bDefault) return 1;
            if (!aDefault && bDefault) return -1;
            return 0; // otherwise preserve the order in which they arrived.
          });
      for (Candle candle : list) {
        c.output(KV.of(key, candle));
      }
    }
  }

  /**
   * This flattening DoFn sorts the grouped values by timestamp in ascending order. It is used in
   * the eviction test.
   */
  public static class FlattenGroupedByTimestampFn
      extends DoFn<KV<String, Iterable<Candle>>, KV<String, Candle>> {
    @ProcessElement
    public void processElement(ProcessContext c) {
      String key = c.element().getKey();
      List<Candle> list = new ArrayList<>();
      for (Candle candle : c.element().getValue()) {
        list.add(candle);
      }
      list.sort(
          (a, b) -> Long.compare(a.getTimestamp().getSeconds(), b.getTimestamp().getSeconds()));
      for (Candle candle : list) {
        c.output(KV.of(key, candle));
      }
    }
  }

  @Test
  public void testBufferSingleCandle() {
    // Arrange
    Candle candle1 =
        Candle.newBuilder()
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
            pipeline
                .apply(Create.of(KV.of("BTC/USD", candle1)))
                // For a single element, grouping isn’t strictly necessary.
                .apply(ParDo.of(new BufferLastCandles(3))))
        .satisfies(
            iterable -> {
              ImmutableList<KV<String, ImmutableList<Candle>>> list =
                  ImmutableList.copyOf(iterable);
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
    // Arrange: a real candle then a default candle.
    Candle realCandle =
        Candle.newBuilder()
            .setOpen(105)
            .setHigh(115)
            .setLow(95)
            .setClose(110) // This close value (110) should be used for replacement.
            .setVolume(1.2)
            .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
            .setCurrencyPair("BTC/USD")
            .build();
    // Default candle (all zeros, including timestamp = 0)
    Candle defaultCandle =
        Candle.newBuilder()
            .setOpen(ZERO)
            .setHigh(ZERO)
            .setLow(ZERO)
            .setClose(ZERO)
            .setVolume(ZERO)
            .setTimestamp(Timestamp.getDefaultInstance())
            .setCurrencyPair(realCandle.getCurrencyPair())
            .build();

    // Act & Assert:
    // Use a GroupByKey and a specialized flattening DoFn that orders non-default candles first.
    PAssert.that(
            pipeline
                .apply(Create.of(KV.of("BTC/USD", realCandle), KV.of("BTC/USD", defaultCandle)))
                .apply("GroupByKey", GroupByKey.create())
                .apply("FlattenGrouped", ParDo.of(new FlattenGroupedWithOrderingFn()))
                .apply(ParDo.of(new BufferLastCandles(3))))
        .satisfies(
            iterable -> {
              ImmutableList<KV<String, ImmutableList<Candle>>> list =
                  ImmutableList.copyOf(iterable);
              // Get the final output (the fully accumulated state)
              KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
              assertEquals("BTC/USD", kv.getKey());
              ImmutableList<Candle> buffer = kv.getValue();
              // We expect two candles in the buffer.
              assertEquals(2, buffer.size());
              // Processing order should be: realCandle processed first, then defaultCandle triggers
              // replacement.
              // After processing, the default candle is replaced with a "filled" candle.
              // Note that the stateful DoFn sorts the buffer by timestamp ascending.
              // The filled candle retains the default candle’s timestamp (0), so it comes first.
              Candle filledCandle = buffer.get(0);
              // Expect the filled candle’s open (and other price fields) to equal
              // realCandle.getClose() i.e. 110.
              assertEquals(realCandle.getClose(), filledCandle.getOpen(), DELTA);
              assertEquals(realCandle.getClose(), filledCandle.getHigh(), DELTA);
              assertEquals(realCandle.getClose(), filledCandle.getLow(), DELTA);
              assertEquals(realCandle.getClose(), filledCandle.getClose(), DELTA);
              assertEquals(ZERO, filledCandle.getVolume(), DELTA);
              // The real candle should be the second element.
              Candle bufferedRealCandle = buffer.get(1);
              assertEquals(realCandle, bufferedRealCandle);
              return null;
            });
    pipeline.run().waitUntilFinish();
  }

  @Test
  public void testBufferExceedsLimitEviction() {
    // Arrange: Create four candles with increasing timestamps.
    Candle candle1 =
        Candle.newBuilder()
            .setOpen(100)
            .setHigh(110)
            .setLow(90)
            .setClose(105)
            .setVolume(1)
            .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
            .setCurrencyPair("BTC/USD")
            .build();
    Candle candle2 =
        Candle.newBuilder()
            .setOpen(105)
            .setHigh(115)
            .setLow(95)
            .setClose(110)
            .setVolume(1.2)
            .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
            .setCurrencyPair("BTC/USD")
            .build();
    Candle candle3 =
        Candle.newBuilder()
            .setOpen(110)
            .setHigh(120)
            .setLow(100)
            .setClose(115)
            .setVolume(1.5)
            .setTimestamp(Timestamp.newBuilder().setSeconds(3000).build())
            .setCurrencyPair("BTC/USD")
            .build();
    Candle candle4 =
        Candle.newBuilder()
            .setOpen(115)
            .setHigh(125)
            .setLow(105)
            .setClose(120)
            .setVolume(1.8)
            .setTimestamp(Timestamp.newBuilder().setSeconds(4000).build())
            .setCurrencyPair("BTC/USD")
            .build();

    // Act & Assert:
    // Use GroupByKey and then flatten the values sorted by timestamp.
    // This ensures that the stateful DoFn processes the candles in ascending order:
    // [candle1, candle2, candle3, candle4]
    // With maxCandles=3, the oldest (candle1) should be evicted.
    PAssert.that(
            pipeline
                .apply(
                    Create.of(
                        KV.of("BTC/USD", candle1),
                        KV.of("BTC/USD", candle2),
                        KV.of("BTC/USD", candle3),
                        KV.of("BTC/USD", candle4)))
                .apply("GroupByKey", GroupByKey.create())
                .apply("FlattenGrouped", ParDo.of(new FlattenGroupedByTimestampFn()))
                .apply(ParDo.of(new BufferLastCandles(3))))
        .satisfies(
            iterable -> {
              ImmutableList<KV<String, ImmutableList<Candle>>> list =
                  ImmutableList.copyOf(iterable);
              KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
              assertEquals("BTC/USD", kv.getKey());
              ImmutableList<Candle> buffer = kv.getValue();
              // With maxCandles = 3 and 4 inputs, the oldest candle (candle1) should be evicted.
              assertEquals(3, buffer.size());
              // The stateful DoFn sorts the buffer by timestamp ascending.
              // Expected final buffer: [candle2, candle3, candle4].
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
            pipeline
                .apply(
                    Create.empty(
                        org.apache.beam.sdk.coders.KvCoder.of(
                            StringUtf8Coder.of(), ProtoCoder.of(Candle.class))))
                .apply(ParDo.of(new BufferLastCandles(3))))
        .satisfies(
            iterable -> {
              assertTrue(!iterable.iterator().hasNext());
              return null;
            });
    pipeline.run().waitUntilFinish();
  }

  @Test
  public void testBufferZeroSize() {
    // Arrange: With a maximum buffer size of zero, the final state should be empty.
    Candle candle1 =
        Candle.newBuilder()
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
            pipeline
                .apply(Create.of(KV.of("BTC/USD", candle1)))
                .apply(ParDo.of(new BufferLastCandles(0))))
        .satisfies(
            iterable -> {
              ImmutableList<KV<String, ImmutableList<Candle>>> list =
                  ImmutableList.copyOf(iterable);
              KV<String, ImmutableList<Candle>> kv = list.get(list.size() - 1);
              assertEquals("BTC/USD", kv.getKey());
              assertTrue(kv.getValue().isEmpty());
              return null;
            });
    pipeline.run().waitUntilFinish();
  }
}
