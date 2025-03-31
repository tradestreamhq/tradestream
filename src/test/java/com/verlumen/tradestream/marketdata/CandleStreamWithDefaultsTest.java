package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.common.base.Suppliers;
import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import java.util.stream.Stream;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.transforms.Create;
import org.joda.time.Duration;
import org.junit.Rule;
import org.junit.Test;

/**
 * Unit tests for CandleStreamWithDefaults.
 */
public class CandleStreamWithDefaultsTest {
    @Rule
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testCompositeTransformEmitsCandlesWithRealTrade() {
        // Arrange: Create a real trade for "BTC/USD".
        com.google.protobuf.Timestamp ts = com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build();
        Trade realTrade = Trade.newBuilder()
            .setTimestamp(ts)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10500.0)
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD", "ETH/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());

        // Act: Apply the composite transform with two currency pairs.
        PAssert.that(
            pipeline.apply("CreateRealTrade", Create.of(KV.of("BTC/USD", realTrade)))
                    .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        Suppliers.ofInstance(currencyPairs),
                        10000.0))
        ).satisfies(iterable -> {
            boolean foundBTC = false;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                if (kv.getKey().equals("BTC/USD")) {
                    foundBTC = true;
                    // We expect that the aggregated candle for BTC/USD reflects the real trade's price.
                    Candle candle = kv.getValue().get(0);
                    assertEquals(10500.0, candle.getClose(), 1e-6);
                }
            }
            assertTrue("Expected to find candle for BTC/USD", foundBTC);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testCompositeTransformEmitsCandlesWithNoRealTrades() {
        // Arrange: Provide an empty input for real trades.
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD", "ETH/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
        PAssert.that(
            pipeline.apply("CreateEmptyRealTrades", Create.empty(
                    org.apache.beam.sdk.coders.KvCoder.of(
                        org.apache.beam.sdk.coders.StringUtf8Coder.of(), 
                        org.apache.beam.sdk.extensions.protobuf.ProtoCoder.of(Trade.class))))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        Suppliers.ofInstance(currencyPairs),
                        10000.0))
        ).satisfies(iterable -> {
            int count = 0;
            // When no real trades exist, the default trade is used.
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                count++;
                Candle candle = kv.getValue().get(0);
                // A default candle (from no real trade) will have 0.0 values.
                assertEquals(0.0, candle.getClose(), 1e-6);
            }
            assertEquals("Expected candles for both currency pairs", 2, count);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testCompositeTransformBufferSize() {
        // Arrange: Create multiple real trades for "BTC/USD" with increasing timestamps.
        com.google.protobuf.Timestamp ts1 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build();
        com.google.protobuf.Timestamp ts2 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1100).build();
        com.google.protobuf.Timestamp ts3 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1200).build();

        Trade trade1 = Trade.newBuilder()
            .setTimestamp(ts1)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10500.0)
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
        Trade trade2 = Trade.newBuilder()
            .setTimestamp(ts2)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10600.0)
            .setVolume(1.0)
            .setTradeId("trade-2")
            .build();
        Trade trade3 = Trade.newBuilder()
            .setTimestamp(ts3)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10700.0)
            .setVolume(1.0)
            .setTradeId("trade-3")
            .build();
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());

        // Act: Apply composite transform with a buffer size of 2.
        PAssert.that(
            pipeline.apply("CreateRealTrades", Create.of(
                KV.of("BTC/USD", trade1),
                KV.of("BTC/USD", trade2),
                KV.of("BTC/USD", trade3)))
            .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                    Duration.standardMinutes(1),
                    Duration.standardSeconds(30),
                    2, // bufferSize = 2
                    Suppliers.ofInstance(currencyPairs),
                    10000.0))
        ).satisfies(iterable -> {
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                if (kv.getKey().equals("BTC/USD")) {
                    // With a buffer size of 2 and 3 trades, only the last two candles should be buffered.
                    assertEquals(2, kv.getValue().size());
                }
            }
            return null;
        });
        pipeline.run().waitUntilFinish();
    }
}
