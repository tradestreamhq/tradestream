package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.junit.Rule;
import org.junit.Test;

/**
 * Unit tests for DefaultTradeGenerator.
 */
public class DefaultTradeGeneratorTest {

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testGenerateDefaultTrade() {
        // Arrange
        String key = "BTC/USD";
        double defaultPrice = 10000.0;

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(defaultPrice))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            // Verify that the synthetic trade is marked appropriately.
            assertTrue(trade.getTradeId().startsWith("DEFAULT-"));
            assertEquals("DEFAULT", trade.getExchange());
            assertEquals(defaultPrice, trade.getPrice(), 1e-6);
            assertEquals(0.0, trade.getVolume(), 1e-6);
            // Since the key is used directly as the currency pair, we expect:
            assertEquals("BTC/USD", trade.getCurrencyPair());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testGenerateDefaultTradeDifferentKey() {
        // Arrange
        String key = "ETH/USD";
        double defaultPrice = 10000.0;

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(defaultPrice))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            assertTrue(trade.getTradeId().startsWith("DEFAULT-"));
            assertEquals("DEFAULT", trade.getExchange());
            assertEquals(defaultPrice, trade.getPrice(), 1e-6);
            assertEquals(0.0, trade.getVolume(), 1e-6);
            assertEquals("ETH/USD", trade.getCurrencyPair());
            return null;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testDefaultPriceConfiguration() {
        // Arrange
        String key = "BTC/USD";
        double customDefaultPrice = 12345.67;

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(customDefaultPrice))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            assertEquals(customDefaultPrice, trade.getPrice(), 1e-6);
            return null;
        });
        pipeline.run().waitUntilFinish();
    }
}
