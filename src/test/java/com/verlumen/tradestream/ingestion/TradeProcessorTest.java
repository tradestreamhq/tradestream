package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import marketdata.Marketdata.Trade;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class TradeProcessorTest {
    private static final long CANDLE_INTERVAL = 60000L;

    TradeProcessor processor = new TradeProcessor(CANDLE_INTERVAL);

    @Before
    public void setUp() {
        processor = new TradeProcessor(CANDLE_INTERVAL);
    }

    @Test
    public void duplicateTrade_isDetected() {
        Trade trade = Trade.newBuilder()
                .setTradeId("123")
                .setTimestamp(System.currentTimeMillis())
                .build();
        
        assertThat(processor.isProcessed(trade)).isFalse(); // First time
        assertThat(processor.isProcessed(trade)).isTrue();  // Second time
    }

    @Test
    public void differentMinutes_sameTrade_notDuplicate() {
        long baseTime = System.currentTimeMillis();
        
        Trade trade1 = Trade.newBuilder()
                .setTradeId("123")
                .setTimestamp(baseTime)
                .build();
        
        Trade trade2 = Trade.newBuilder()
                .setTradeId("123")
                .setTimestamp(baseTime + CANDLE_INTERVAL)
                .build();
        
        assertThat(processor.isProcessed(trade1)).isFalse();
        assertThat(processor.isProcessed(trade2)).isFalse();
    }
}
