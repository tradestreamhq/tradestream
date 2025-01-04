package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static com.google.protobuf.util.Timestamps.fromMillis;

import com.verlumen.tradestream.marketdata.Trade;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class TradeProcessorTest {
    private static final long CANDLE_INTERVAL = 60000L;

    private TradeProcessor processor;

    @Before
    public void setUp() {
        processor = TradeProcessor.create(CANDLE_INTERVAL);
    }

    @Test
    public void duplicateTrade_isDetected() {
        long baseTime = System.currentTimeMillis();
        Trade trade = Trade.newBuilder()
                .setTradeId("123")
                .setTimestamp(fromMillis(baseTime))
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
                .setTimestamp(fromMillis(baseTime + CANDLE_INTERVAL))
                .build();
        
        assertThat(processor.isProcessed(trade1)).isFalse();
        assertThat(processor.isProcessed(trade2)).isFalse();
    }
}
