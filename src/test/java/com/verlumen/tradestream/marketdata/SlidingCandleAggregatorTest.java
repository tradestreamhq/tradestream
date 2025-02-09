package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.SlidingCandleAggregator.CandleAccumulator;
import com.verlumen.tradestream.marketdata.SlidingCandleAggregator.CandleCombineFn;
import com.verlumen.tradestream.marketdata.Trade;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Duration;
import org.joda.time.Instant;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;

public class SlidingCandleAggregatorTest {
    private static final double DELTA = 1e-6;
    private static final double ZERO = 0.0;

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Before
    public void setUp() {
        // Register coders for protobuf messages.
        pipeline.getCoderRegistry().registerCoderForClass(Trade.class, ProtoCoder.of(Trade.class));
        pipeline.getCoderRegistry().registerCoderForClass(Candle.class, ProtoCoder.of(Candle.class));
    }

    @Test
    public void testAggregateSingleTrade() {
        // Arrange
        Instant now = Instant.now();
        Timestamp ts = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
        Trade trade = Trade.newBuilder()
                .setTimestamp(ts)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10000)
                .setVolume(0.5)
                .setTradeId("trade1")
                .build();

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", trade)))
                    .apply(new SlidingCandleAggregator(Duration.standardMinutes(1), Duration.standardSeconds(30)))
        ).satisfies(iterable -> {
            // Since we have a single element, we expect one KV.
            KV<String, Candle> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            Candle candle = kv.getValue();
            assertEquals(10000, candle.getOpen(), DELTA);
            assertEquals(10000, candle.getHigh(), DELTA);
            assertEquals(10000, candle.getLow(), DELTA);
            assertEquals(10000, candle.getClose(), DELTA);
            assertEquals(0.5, candle.getVolume(), DELTA);
            assertEquals(ts, candle.getTimestamp());
            assertEquals("BTC/USD", candle.getCurrencyPair());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testAggregateMultipleTradesSameWindow() {
        // Arrange
        Instant now = Instant.now();
        Timestamp ts1 = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
        Timestamp ts2 = Timestamp.newBuilder().setSeconds(now.plus(Duration.standardSeconds(10)).getMillis() / 1000).build();
        Trade trade1 = Trade.newBuilder()
                .setTimestamp(ts1)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10000)
                .setVolume(0.5)
                .setTradeId("trade1")
                .build();
        Trade trade2 = Trade.newBuilder()
                .setTimestamp(ts2)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10100)
                .setVolume(0.7)
                .setTradeId("trade2")
                .build();

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of("BTC/USD", trade1), KV.of("BTC/USD", trade2)))
                    .apply(new SlidingCandleAggregator(Duration.standardMinutes(1), Duration.standardSeconds(30)))
        ).satisfies(iterable -> {
            // Since the Combine.perKey may output multiple elements (if the same key appears in multiple windows)
            // we iterate through them to check one window where both trades were combined.
            boolean found = false;
            for (KV<String, Candle> kv : iterable) {
                if ("BTC/USD".equals(kv.getKey())) {
                    Candle candle = kv.getValue();
                    // For the window that contains both trades, the open should be 10000 and close 10100.
                    if (candle.getOpen() == 10000 && candle.getClose() == 10100) {
                        assertEquals(10000, candle.getOpen(), DELTA);
                        assertEquals(10100, candle.getHigh(), DELTA);
                        assertEquals(10000, candle.getLow(), DELTA);
                        assertEquals(10100, candle.getClose(), DELTA);
                        assertEquals(1.2, candle.getVolume(), DELTA);
                        assertEquals(ts1, candle.getTimestamp()); // open timestamp
                        found = true;
                    }
                }
            }
            assertTrue("Expected a window with both trades aggregated", found);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testAggregateNoTrades() {
        // Arrange & Act: Create an empty PCollection.
        // Because there are no keys, the output should be empty.
        PAssert.that(
            pipeline.apply(Create.empty(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade.class))))
                    .apply(new SlidingCandleAggregator(Duration.standardMinutes(1), Duration.standardSeconds(30)))
        ).empty();
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testMergeAccumulators() {
        // Arrange
        CandleCombineFn combineFn = new CandleCombineFn();
        CandleAccumulator acc1 = combineFn.createAccumulator();
        CandleAccumulator acc2 = combineFn.createAccumulator();

        Instant now = Instant.now();
        Timestamp ts1 = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
        Timestamp ts2 = Timestamp.newBuilder().setSeconds(now.plus(Duration.standardSeconds(10)).getMillis() / 1000).build();

        Trade trade1 = Trade.newBuilder()
                .setTimestamp(ts1)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10000)
                .setVolume(0.5)
                .setTradeId("trade1")
                .build();
        Trade trade2 = Trade.newBuilder()
                .setTimestamp(ts2)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10100)
                .setVolume(0.7)
                .setTradeId("trade2")
                .build();

        acc1 = combineFn.addInput(acc1, trade1);
        acc2 = combineFn.addInput(acc2, trade2);

        // Act
        CandleAccumulator mergedAcc = combineFn.mergeAccumulators(java.util.Arrays.asList(acc1, acc2));
        Candle candle = combineFn.extractOutput(mergedAcc);

        // Assert
        assertEquals(10000, mergedAcc.open, DELTA);
        assertEquals(10100, mergedAcc.high, DELTA);
        assertEquals(10000, mergedAcc.low, DELTA);
        assertEquals(10100, mergedAcc.close, DELTA);
        assertEquals(1.2, mergedAcc.volume, DELTA);
        assertEquals(ts1, mergedAcc.openTimestamp);
        assertEquals("BTC/USD", mergedAcc.currencyPair);
        assertEquals(10000, candle.getOpen(), DELTA);
    }

    @Test
    public void testAddInputFirstTrade() {
        // Arrange
        CandleCombineFn combineFn = new CandleCombineFn();
        CandleAccumulator accumulator = combineFn.createAccumulator();
        Instant now = Instant.now();
        Timestamp ts = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
        Trade trade = Trade.newBuilder()
                .setTimestamp(ts)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10000)
                .setVolume(0.5)
                .setTradeId("trade1")
                .build();

        // Act
        CandleAccumulator updatedAcc = combineFn.addInput(accumulator, trade);

        // Assert
        assertEquals(10000, updatedAcc.open, DELTA);
        assertEquals(10000, updatedAcc.high, DELTA);
        assertEquals(10000, updatedAcc.low, DELTA);
        assertEquals(10000, updatedAcc.close, DELTA);
        assertEquals(0.5, updatedAcc.volume, DELTA);
        assertEquals(ts, updatedAcc.openTimestamp);
        assertEquals(ts, updatedAcc.closeTimestamp);
        assertEquals("BTC/USD", updatedAcc.currencyPair);
        assertEquals(false, updatedAcc.firstTrade);
    }

    @Test
    public void testAddInputSubsequentTrade() {
        // Arrange
        CandleCombineFn combineFn = new CandleCombineFn();
        CandleAccumulator accumulator = combineFn.createAccumulator();
        Instant now = Instant.now();
        Timestamp ts1 = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
        Timestamp ts2 = Timestamp.newBuilder().setSeconds(now.plus(Duration.standardSeconds(10)).getMillis() / 1000).build();
        Trade trade1 = Trade.newBuilder()
                .setTimestamp(ts1)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10000)
                .setVolume(0.5)
                .setTradeId("trade1")
                .build();
        Trade trade2 = Trade.newBuilder()
                .setTimestamp(ts2)
                .setExchange("BINANCE")
                .setCurrencyPair("BTC/USD")
                .setPrice(10100)
                .setVolume(0.7)
                .setTradeId("trade2")
                .build();

        accumulator = combineFn.addInput(accumulator, trade1);

        // Act
        CandleAccumulator updatedAcc = combineFn.addInput(accumulator, trade2);

        // Assert
        assertEquals(10000, updatedAcc.open, DELTA);
        assertEquals(10100, updatedAcc.high, DELTA);
        assertEquals(10000, updatedAcc.low, DELTA);
        assertEquals(10100, updatedAcc.close, DELTA);
        assertEquals(1.2, updatedAcc.volume, DELTA);
        assertEquals(ts1, updatedAcc.openTimestamp);
        assertEquals(ts2, updatedAcc.closeTimestamp);
        assertEquals("BTC/USD", updatedAcc.currencyPair);
        assertEquals(false, updatedAcc.firstTrade);
    }
}
