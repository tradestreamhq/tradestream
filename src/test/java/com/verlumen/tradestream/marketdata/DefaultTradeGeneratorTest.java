package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.CurrencyPair;
import java.math.BigDecimal;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.junit.Rule;
import org.junit.Test;

public class DefaultTradeGeneratorTest {

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testGenerateDefaultTrade() {
        // Arrange
        String key = "BTC/USD";
        BigDecimal defaultPrice = new BigDecimal("10000");

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(defaultPrice)))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            assertTrue(trade.getTradeId().startsWith("DEFAULT-"));
            assertEquals(defaultPrice, trade.getPrice());
            assertEquals(BigDecimal.ZERO, trade.getVolume());
            assertEquals("DEFAULT", trade.getExchange());
            assertEquals("BTC", trade.getCurrencyPair().getBase());
            assertEquals("USD", trade.getCurrencyPair().getQuote());
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testGenerateDefaultTradeDifferentKey() {
        // Arrange
        String key = "ETH/USD";
        BigDecimal defaultPrice = new BigDecimal("10000");

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(defaultPrice)))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            assertTrue(trade.getTradeId().startsWith("DEFAULT-"));
            assertEquals(defaultPrice, trade.getPrice());
            assertEquals(BigDecimal.ZERO, trade.getVolume());
            assertEquals("DEFAULT", trade.getExchange());
            assertEquals("ETH", trade.getCurrencyPair().getBase());
            assertEquals("USD", trade.getCurrencyPair().getQuote());
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }

    @Test
    public void testDefaultPriceConfiguration() {
        // Arrange
        String key = "BTC/USD";
        BigDecimal customDefaultPrice = new BigDecimal("12345.67");

        // Act & Assert
        PAssert.that(
            pipeline.apply(Create.of(KV.of(key, (Void) null)))
                    .apply(new DefaultTradeGenerator(customDefaultPrice)))
        ).satisfies(iterable -> {
            KV<String, Trade> kv = iterable.iterator().next();
            assertEquals(key, kv.getKey());
            Trade trade = kv.getValue();
            assertEquals(customDefaultPrice, trade.getPrice());
            return iterable;
        });
        pipeline.run().waitUntilFinish();
    }
}
