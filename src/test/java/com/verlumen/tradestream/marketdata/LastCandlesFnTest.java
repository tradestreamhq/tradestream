package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.CurrencyPair;
import com.verlumen.tradestream.marketdata.LastCandlesFn.BufferLastCandles;
import org.apache.beam.sdk.coders.ProtoCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Instant;
import org.junit.Rule;
import org.junit.Test;
import java.math.BigDecimal;
import java.util.LinkedList;

public class LastCandlesFnTest {

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testBufferSingleCandle() {
        // Arrange
        Candle candle1 = Candle.newBuilder()
                .setOpen(new BigDecimal("100"))
                .setHigh(new BigDecimal("110"))
                .setLow(new BigDecimal("90"))
                .setClose(new BigDecimal("105"))
                .setVolume(new BigDecimal("1"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
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
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferDefaultCandleReplacement() {
        // Arrange: First, add a real candle, then add a default (dummy) candle.
        Candle realCandle = Candle.newBuilder()
                .setOpen(new BigDecimal("105"))
                .setHigh(new BigDecimal("115"))
                .setLow(new BigDecimal("95"))
                .setClose(new BigDecimal("110"))
                .setVolume(new BigDecimal("1.2"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
                .build();
        // Create a default candle (no trades)
        Candle defaultCandle = Candle.newBuilder()
                .setOpen(BigDecimal.ZERO)
                .setHigh(BigDecimal.ZERO)
                .setLow(BigDecimal.ZERO)
                .setClose(BigDecimal.ZERO)
                .setVolume(BigDecimal.ZERO)
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
            assertEquals(realCandle.getClose(), filledCandle.getOpen());
            assertEquals(realCandle.getClose(), filledCandle.getHigh());
            assertEquals(realCandle.getClose(), filledCandle.getLow());
            assertEquals(realCandle.getClose(), filledCandle.getClose());
            assertEquals(BigDecimal.ZERO, filledCandle.getVolume());
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferExceedsLimitEviction() {
        // Arrange
        Candle candle1 = Candle.newBuilder()
                .setOpen(new BigDecimal("100"))
                .setHigh(new BigDecimal("110"))
                .setLow(new BigDecimal("90"))
                .setClose(new BigDecimal("105"))
                .setVolume(new BigDecimal("1"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
                .build();
        Candle candle2 = Candle.newBuilder()
                .setOpen(new BigDecimal("105"))
                .setHigh(new BigDecimal("115"))
                .setLow(new BigDecimal("95"))
                .setClose(new BigDecimal("110"))
                .setVolume(new BigDecimal("1.2"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
                .build();
        Candle candle3 = Candle.newBuilder()
                .setOpen(new BigDecimal("110"))
                .setHigh(new BigDecimal("120"))
                .setLow(new BigDecimal("100"))
                .setClose(new BigDecimal("115"))
                .setVolume(new BigDecimal("1.5"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(3000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
                .build();
        Candle candle4 = Candle.newBuilder()
                .setOpen(new BigDecimal("115"))
                .setHigh(new BigDecimal("125"))
                .setLow(new BigDecimal("105"))
                .setClose(new BigDecimal("120"))
                .setVolume(new BigDecimal("1.8"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(4000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
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
            return iterable;
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
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testBufferZeroSize() {
        // Arrange
        Candle candle1 = Candle.newBuilder()
                .setOpen(new BigDecimal("100"))
                .setHigh(new BigDecimal("110"))
                .setLow(new BigDecimal("90"))
                .setClose(new BigDecimal("105"))
                .setVolume(new BigDecimal("1"))
                .setTimestamp(Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair(CurrencyPair.newBuilder().setBase("BTC").setQuote("USD").build())
                .build();

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", candle1)))
                    .apply(ParDo.of(new BufferLastCandles(0)))
        ).satisfies(iterable -> {
            KV<String, ImmutableList<Candle>> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            assertTrue(kv.getValue().isEmpty());
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }
}
