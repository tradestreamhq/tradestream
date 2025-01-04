package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.*;

import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.Candle;
import org.junit.Test;
import org.junit.runner.RunWith;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;

@RunWith(TestParameterInjector.class)
public class CandleBuilderTest {
    private static final String TEST_PAIR = "BTC/USD";
    private static final Timestamp TEST_TIMESTAMP = fromMillis(1622548800000L);

    @Test
    public void firstTrade_setsAllPrices() {
        CandleBuilder builder = new CandleBuilder(TEST_PAIR, TEST_TIMESTAMP);
        Trade trade = createTrade(100.0, 1.0);
        
        builder.addTrade(trade);
        Candle candle = builder.build();
        
        assertThat(candle.getOpen()).isEqualTo(100.0);
        assertThat(candle.getHigh()).isEqualTo(100.0);
        assertThat(candle.getLow()).isEqualTo(100.0);
        assertThat(candle.getClose()).isEqualTo(100.0);
    }

    @Test
    public void multipleTradesUpdateHighLowClose() {
        CandleBuilder builder = new CandleBuilder(TEST_PAIR, TEST_TIMESTAMP);
        
        builder.addTrade(createTrade(100.0, 1.0));
        builder.addTrade(createTrade(150.0, 1.0));
        builder.addTrade(createTrade(80.0, 1.0));
        
        Candle candle = builder.build();
        assertThat(candle.getOpen()).isEqualTo(100.0);
        assertThat(candle.getHigh()).isEqualTo(150.0);
        assertThat(candle.getLow()).isEqualTo(80.0);
        assertThat(candle.getClose()).isEqualTo(80.0);
    }

    private Trade createTrade(double price, double volume) {
        return Trade.newBuilder()
                .setTimestamp(TEST_TIMESTAMP)
                .setCurrencyPair(TEST_PAIR)
                .setPrice(price)
                .setVolume(volume)
                .build();
    }
}
