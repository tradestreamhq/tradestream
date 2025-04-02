package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.common.collect.ImmutableList;
import java.util.Arrays;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.transforms.Create;
import org.joda.time.Duration;
import org.junit.Rule;
import org.junit.Test;

import java.util.List;
import java.util.ArrayList;

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

        // Act: Apply the composite transform with two currency pairs.
        PAssert.that(
            pipeline.apply("CreateRealTrade", Create.of(KV.of("BTC/USD", realTrade)))
                    .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        Arrays.asList("BTC/USD", "ETH/USD"),
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
        PAssert.that(
            pipeline.apply("CreateEmptyRealTrades", Create.empty(
                    org.apache.beam.sdk.coders.KvCoder.of(
                        org.apache.beam.sdk.coders.StringUtf8Coder.of(), 
                        org.apache.beam.sdk.extensions.protobuf.ProtoCoder.of(Trade.class))))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                        Duration.standardMinutes(1),
                        Duration.standardSeconds(30),
                        5,
                        Arrays.asList("BTC/USD", "ETH/USD"),
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
                    Arrays.asList("BTC/USD"),
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

    @Test
    public void testSyntheticCandleInterpolation() {
        // Arrange: Create two real candles with a gap
        com.google.protobuf.Timestamp ts1 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build();
        com.google.protobuf.Timestamp ts2 = com.google.protobuf.Timestamp.newBuilder().setSeconds(2000).build();
        com.google.protobuf.Timestamp ts3 = com.google.protobuf.Timestamp.newBuilder().setSeconds(3000).build();
        
        Trade trade1 = Trade.newBuilder()
            .setTimestamp(ts1)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10000.0)
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
            
        Trade trade2 = Trade.newBuilder()
            .setTimestamp(ts2)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(11000.0)
            .setVolume(1.0)
            .setTradeId("trade-2")
            .build();

        // Act: Apply the composite transform
        PAssert.that(
            pipeline.apply("CreateRealTrades", Create.of(
                    KV.of("BTC/USD", trade1),
                    KV.of("BTC/USD", trade2)))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                    Duration.standardMinutes(1),
                    Duration.standardSeconds(30),
                    5,
                    Arrays.asList("BTC/USD"),
                    10000.0))
        ).satisfies(iterable -> {
            boolean foundSynthetic = false;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                if (kv.getKey().equals("BTC/USD")) {
                    ImmutableList<Candle> candles = kv.getValue();
                    // We should have at least 2 candles
                    assertTrue("Expected at least 2 candles", candles.size() >= 2);
                    
                    // Find the synthetic candle between the two real candles
                    for (int i = 0; i < candles.size() - 1; i++) {
                        Candle current = candles.get(i);
                        Candle next = candles.get(i + 1);
                        
                        if (current.getTimestamp().getSeconds() == ts1.getSeconds() &&
                            next.getTimestamp().getSeconds() == ts2.getSeconds()) {
                            // The candle between these should be synthetic
                            if (i + 1 < candles.size()) {
                                Candle synthetic = candles.get(i + 1);
                                assertTrue("Expected synthetic candle", synthetic.getSynthetic());
                                // The interpolated price should be between 10000 and 11000
                                assertTrue("Interpolated price should be between 10000 and 11000",
                                    synthetic.getClose() > 10000 && synthetic.getClose() < 11000);
                                foundSynthetic = true;
                            }
                        }
                    }
                }
            }
            assertTrue("Expected to find synthetic candle", foundSynthetic);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testWindowAlignment() {
        // Arrange: Create real trades at specific timestamps
        com.google.protobuf.Timestamp ts1 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build();
        com.google.protobuf.Timestamp ts2 = com.google.protobuf.Timestamp.newBuilder().setSeconds(1060).build(); // 1 minute later
        
        Trade trade1 = Trade.newBuilder()
            .setTimestamp(ts1)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(10000.0)
            .setVolume(1.0)
            .setTradeId("trade-1")
            .build();
            
        Trade trade2 = Trade.newBuilder()
            .setTimestamp(ts2)
            .setExchange("BINANCE")
            .setCurrencyPair("BTC/USD")
            .setPrice(11000.0)
            .setVolume(1.0)
            .setTradeId("trade-2")
            .build();

        // Act: Apply the composite transform with 1-minute windows and 30-second slides
        PAssert.that(
            pipeline.apply("CreateRealTrades", Create.of(
                    KV.of("BTC/USD", trade1),
                    KV.of("BTC/USD", trade2)))
                .apply("ApplyCompositeTransform", new CandleStreamWithDefaults(
                    Duration.standardMinutes(1),
                    Duration.standardSeconds(30),
                    5,
                    Arrays.asList("BTC/USD"),
                    10000.0))
        ).satisfies(iterable -> {
            boolean foundOverlappingWindow = false;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                if (kv.getKey().equals("BTC/USD")) {
                    ImmutableList<Candle> candles = kv.getValue();
                    // We should have at least 2 candles
                    assertTrue("Expected at least 2 candles", candles.size() >= 2);
                    
                    // Find candles that overlap in time
                    for (int i = 0; i < candles.size() - 1; i++) {
                        Candle current = candles.get(i);
                        Candle next = candles.get(i + 1);
                        
                        // Check if these candles overlap in time
                        long currentEnd = current.getTimestamp().getSeconds() + 60; // 1-minute window
                        long nextStart = next.getTimestamp().getSeconds();
                        
                        if (currentEnd > nextStart) {
                            foundOverlappingWindow = true;
                            // Verify that the overlapping candles have consistent prices
                            assertTrue("Overlapping candles should have consistent prices",
                                Math.abs(current.getClose() - next.getOpen()) < 1e-6);
                        }
                    }
                }
            }
            assertTrue("Expected to find overlapping windows", foundOverlappingWindow);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test(expected = IllegalArgumentException.class)
    public void testBufferSizeValidation() {
        // Test with buffer size below minimum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            0, // Invalid buffer size
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testBufferSizeValidationTooLarge() {
        // Test with buffer size above maximum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            10001, // Invalid buffer size
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test
    public void testBufferSizeEdgeCases() {
        // Test with minimum valid buffer size
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            1, // Minimum valid buffer size
            Arrays.asList("BTC/USD"),
            10000.0);

        // Test with maximum valid buffer size
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            10000, // Maximum valid buffer size
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test
    public void testBufferSizeWithDifferentTimeframes() {
        // Test with 1-minute candles (24 hours of history)
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            1440, // 24 hours of 1-minute candles
            Arrays.asList("BTC/USD"),
            10000.0);

        // Test with 5-minute candles (24 hours of history)
        new CandleStreamWithDefaults(
            Duration.standardMinutes(5),
            Duration.standardSeconds(30),
            288, // 24 hours of 5-minute candles
            Arrays.asList("BTC/USD"),
            10000.0);

        // Test with 15-minute candles (24 hours of history)
        new CandleStreamWithDefaults(
            Duration.standardMinutes(15),
            Duration.standardSeconds(30),
            96, // 24 hours of 15-minute candles
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testWindowDurationValidation() {
        // Test with window duration below minimum
        new CandleStreamWithDefaults(
            Duration.standardSeconds(0), // Invalid window duration
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testWindowDurationValidationTooLarge() {
        // Test with window duration above maximum
        new CandleStreamWithDefaults(
            Duration.standardHours(25), // Invalid window duration
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testSlideDurationValidation() {
        // Test with slide duration below minimum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(0), // Invalid slide duration
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testSlideDurationValidationTooLarge() {
        // Test with slide duration larger than window duration
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardMinutes(2), // Invalid slide duration
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testCurrencyPairValidationNull() {
        // Test with null currency pair
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList((String)null),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testCurrencyPairValidationEmpty() {
        // Test with empty currency pair
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList(""),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testCurrencyPairValidationInvalidFormat() {
        // Test with invalid currency pair format
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTCUSD"), // Invalid format
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testDefaultPriceValidationTooSmall() {
        // Test with default price below minimum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD"),
            0.00001); // Invalid default price
    }

    @Test(expected = IllegalArgumentException.class)
    public void testWindowSlideRatioValidation() {
        // Test with window/slide ratio too large
        new CandleStreamWithDefaults(
            Duration.standardHours(1),
            Duration.standardSeconds(1), // This creates too many overlapping windows
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test
    public void testValidParameterCombinations() {
        // Test various valid combinations
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD", "ETH/USD"),
            10000.0);

        new CandleStreamWithDefaults(
            Duration.standardMinutes(5),
            Duration.standardSeconds(30),
            10,
            Arrays.asList("BTC/USD"),
            0.0001); // Minimum valid price

        new CandleStreamWithDefaults(
            Duration.standardHours(1),
            Duration.standardMinutes(1),
            100,
            Arrays.asList("BTC/USD", "ETH/USD", "XRP/USD"),
            1000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testTooManyCurrencyPairs() {
        // Create a list with more than MAX_CURRENCY_PAIRS (100) currency pairs
        List<String> pairs = new ArrayList<>();
        for (int i = 0; i < 101; i++) {
            pairs.add(String.format("PAIR%d/USD", i));
        }
        
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            pairs,
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testDuplicateCurrencyPairs() {
        // Test with duplicate currency pairs (case-insensitive)
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD", "btc/usd"), // Same pair with different case
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testDefaultPriceTooLarge() {
        // Test with default price above maximum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD"),
            1_000_000_001.0); // Price above MAX_DEFAULT_PRICE
    }

    @Test(expected = IllegalArgumentException.class)
    public void testWindowSlideRatioTooSmall() {
        // Test with window/slide ratio below minimum
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardMinutes(1), // Equal window and slide duration
            5,
            Arrays.asList("BTC/USD"),
            10000.0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testMemoryUsageExceeded() {
        // Test with configuration that would exceed memory limit
        // Using large buffer size and many currency pairs
        List<String> pairs = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            pairs.add(String.format("PAIR%d/USD", i));
        }
        
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            20000, // Large buffer size
            pairs,
            10000.0);
    }

    @Test
    public void testValidEdgeCases() {
        // Test with maximum allowed currency pairs
        List<String> maxPairs = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            maxPairs.add(String.format("PAIR%d/USD", i));
        }
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            maxPairs,
            10000.0);

        // Test with maximum allowed default price
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            5,
            Arrays.asList("BTC/USD"),
            1_000_000_000.0);

        // Test with minimum valid window/slide ratio
        new CandleStreamWithDefaults(
            Duration.standardMinutes(2),
            Duration.standardMinutes(1),
            5,
            Arrays.asList("BTC/USD"),
            10000.0);

        // Test with maximum valid window/slide ratio
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1000),
            Duration.standardMinutes(1),
            5,
            Arrays.asList("BTC/USD"),
            10000.0);

        // Test with maximum valid memory usage
        List<String> memoryTestPairs = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            memoryTestPairs.add(String.format("PAIR%d/USD", i));
        }
        new CandleStreamWithDefaults(
            Duration.standardMinutes(1),
            Duration.standardSeconds(30),
            10000, // Large buffer size
            memoryTestPairs,
            10000.0);
    }
}
