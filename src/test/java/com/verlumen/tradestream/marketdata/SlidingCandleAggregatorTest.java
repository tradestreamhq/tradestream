package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.CurrencyPair;
import com.verlumen.tradestream.marketdata.SlidingCandleAggregator.CandleAccumulator;
import com.verlumen.tradestream.marketdata.SlidingCandleAggregator.CandleCombineFn;
import com.verlumen.tradestream.marketdata.Trade;
import java.util.Arrays;
import org.apache.beam.sdk.coders.ProtoCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Duration;
import org.joda.time.Instant;
import org.junit.Rule;
import org.junit.Test;

public class SlidingCandleAggregatorTest {
    private static final double ZERO = 0.0;

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

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
            KV<String, Candle> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            Candle candle = kv.getValue();
            assertEquals(10000, candle.getOpen());
            assertEquals(10000, candle.getHigh());
            assertEquals(10000, candle.getLow());
            assertEquals(10000, candle.getClose());
            assertEquals(0.5, candle.getVolume());
            assertEquals(ts, candle.getTimestamp());
            assertEquals("BTC/USD", candle.getCurrencyPair().getBase() + "/" + candle.getCurrencyPair().getQuote());
            return iterable;
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
            KV<String, Candle> kv = iterable.iterator().next();
            assertEquals("BTC/USD", kv.getKey());
            Candle candle = kv.getValue();
            assertEquals(10000, candle.getOpen());
            assertEquals(10100, candle.getHigh());
            assertEquals(10000, candle.getLow());
            assertEquals(10100, candle.getClose());
            assertEquals(1.2, candle.getVolume());
            assertEquals(ts1, candle.getTimestamp()); // Earliest timestamp
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testAggregateNoTrades() {
        // Arrange & Act & Assert: When no trades are provided, the CombineFn should produce a default candle.
        PAssert.that(
            pipeline.apply(Create.empty(org.apache.beam.sdk.coders.KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade.class))))
                    .apply(new SlidingCandleAggregator(Duration.standardMinutes(1), Duration.standardSeconds(30)))
        ).satisfies(iterable -> {
            Candle candle = iterable.iterator().next().getValue();
            assertEquals(ZERO, candle.getOpen());
            assertEquals(ZERO, candle.getHigh());
            assertEquals(ZERO, candle.getLow());
            assertEquals(ZERO, candle.getClose());
            assertEquals(ZERO, candle.getVolume());
            assertEquals(Timestamp.getDefaultInstance(), candle.getTimestamp());
            return iterable;
        });
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
        CandleAccumulator mergedAcc = combineFn.mergeAccumulators(Arrays.asList(acc1, acc2));
        Candle candle = combineFn.extractOutput(mergedAcc);

        // Assert
        assertEquals(10000, mergedAcc.open);
        assertEquals(10100, mergedAcc.high);
        assertEquals(10000, mergedAcc.low);
        assertEquals(10100, mergedAcc.close);
        assertEquals(1.2, mergedAcc.volume);
        assertEquals(ts1, mergedAcc.timestamp);
        assertEquals("BTC/USD", mergedAcc.currencyPair);
        assertEquals(10000, candle.getOpen());
        return;
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
        assertEquals(10000, updatedAcc.open);
        assertEquals(10000, updatedAcc.high);
        assertEquals(10000, updatedAcc.low);
        assertEquals(10000, updatedAcc.close);
        assertEquals(0.5, updatedAcc.volume);
        assertEquals(ts, updatedAcc.timestamp);
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
        assertEquals(10000, updatedAcc.open);
        assertEquals(10100, updatedAcc.high);
        assertEquals(10000, updatedAcc.low);
        assertEquals(10100, updatedAcc.close);
        assertEquals(1.2, updatedAcc.volume);
        assertEquals(ts1, updatedAcc.timestamp);
        assertEquals("BTC/USD", updatedAcc.currencyPair);
        assertEquals(false, updatedAcc.firstTrade);
    }
}
