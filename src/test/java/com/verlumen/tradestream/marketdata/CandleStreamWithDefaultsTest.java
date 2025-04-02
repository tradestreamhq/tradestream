package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.common.base.Suppliers;
import com.google.common.collect.ImmutableList;
import com.google.inject.Provider;
import com.verlumen.tradestream.instruments.CurrencyPair;
import java.util.function.Supplier;
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
        // Arrange: Create a single real trade.
        Trade trade = Trade.newBuilder()
            .setPrice(50000.0)
            .setCurrencyPair("BTC/USD")
            .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build())
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD", "ETH/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());

        // Create a Provider that returns a Supplier of currency pairs
        Supplier<List<CurrencyPair>> currencyPairSupplier = 
            () -> () -> currencyPairs;

        // Act: Apply the composite transform with two currency pairs.
        PAssert.that(
            pipeline.apply("CreateRealTrades", Create.of(KV.of("BTC/USD", trade)))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        currencyPairSupplier,
                        10000.0))
        ).satisfies(iterable -> {
            boolean foundBTC = false;
            boolean foundETH = false;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                if (kv.getKey().equals("BTC/USD")) {
                    foundBTC = true;
                } else if (kv.getKey().equals("ETH/USD")) {
                    foundETH = true;
                }
                assertTrue(!kv.getValue().isEmpty());
            }
            assertTrue(foundBTC);
            assertTrue(foundETH);
            return null;
        });
        pipeline.run();
    }

    @Test
    public void testCompositeTransformEmitsCandlesWithNoRealTrades() {
        // Arrange: Provide an empty input for real trades.
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD", "ETH/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
            
        // Create a Provider that returns a Supplier of currency pairs
        Supplier<List<CurrencyPair>> currencyPairSupplier = 
            () -> currencyPairs;
            
        PAssert.that(
            pipeline.apply("CreateEmptyRealTrades", Create.empty(
                    org.apache.beam.sdk.coders.KvCoder.of(
                    org.apache.beam.sdk.coders.StringUtf8Coder.of(),
                    org.apache.beam.sdk.extensions.protobuf.ProtoCoder.of(Trade.class))))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        currencyPairSupplier,
                        10000.0))
        ).satisfies(iterable -> {
            int count = 0;
            boolean foundBTC = false;
            boolean foundETH = false;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                count++;
                if (kv.getKey().equals("BTC/USD")) {
                    foundBTC = true;
                    // The buffer should contain synthetic trades.
                    assertEquals(10000.0, kv.getValue().get(0).getOpen(), 0.0);
                    assertEquals(10000.0, kv.getValue().get(0).getClose(), 0.0);
                } else if (kv.getKey().equals("ETH/USD")) {
                    foundETH = true;
                    // The buffer should contain synthetic trades.
                    assertEquals(10000.0, kv.getValue().get(0).getOpen(), 0.0);
                    assertEquals(10000.0, kv.getValue().get(0).getClose(), 0.0);
                }
            }
            assertEquals(2, count);
            assertTrue(foundBTC);
            assertTrue(foundETH);
            return null;
        });
        pipeline.run();
    }

    @Test
    public void testCompositeTransformBufferSize() {
        // Arrange: Create 3 trades with different prices.
        Trade trade1 = Trade.newBuilder()
            .setPrice(50000.0)
            .setCurrencyPair("BTC/USD")
            .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build())
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
        Trade trade2 = Trade.newBuilder()
            .setPrice(51000.0)
            .setCurrencyPair("BTC/USD")
            .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(1001).build())
            .setVolume(1.0)
            .setTradeId("trade-2")
            .build();
        Trade trade3 = Trade.newBuilder()
            .setPrice(52000.0)
            .setCurrencyPair("BTC/USD")
            .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(1002).build())
            .setVolume(1.0)
            .setTradeId("trade-3")
            .build();
        ImmutableList<CurrencyPair> currencyPairs = Stream.of("BTC/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
            
        // Create a Provider that returns a Supplier of currency pairs
        Supplier<List<CurrencyPair>> currencyPairSupplier = 
            () -> currencyPairs;

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
                    currencyPairSupplier,
                    10000.0))
        ).satisfies(iterable -> {
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                // The buffer size is 2, so we expect only the last 2 trades in the candle list.
                assertEquals(2, kv.getValue().size());
                
                // First candle should be from trade2
                assertEquals(51000.0, kv.getValue().get(0).getClose(), 0.0);
                
                // Second candle should be from trade3
                assertEquals(52000.0, kv.getValue().get(1).getClose(), 0.0);
            }
            return null;
        });
        pipeline.run();
    }
}
