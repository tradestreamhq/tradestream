package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import marketdata.Marketdata.Trade;
import marketdata.Marketdata.Candle;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;

@RunWith(TestParameterInjector.class)
public class CandleManagerTest {
    private static final long CANDLE_INTERVAL = 60000L;
    private static final String TEST_PAIR = "BTC/USD";
    
    @Mock private CandlePublisher mockPublisher;
    @Mock private PriceTracker mockPriceTracker;
    private CandleManager manager;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        manager = new CandleManager(CANDLE_INTERVAL, mockPublisher, mockPriceTracker);
    }

    @Test
    public void processTrade_createsNewBuilder() {
        long timestamp = System.currentTimeMillis();
        Trade trade = createTestTrade(timestamp);
        
        manager.processTrade(trade);
        
        assertThat(manager.getActiveBuilderCount()).isEqualTo(1);
    }

    @Test
    public void processTrade_updatesLastPrice() {
        Trade trade = createTestTrade(System.currentTimeMillis());
        manager.processTrade(trade);
        verify(mockPriceTracker).updateLastPrice(TEST_PAIR, trade.getPrice());
    }

    @Test
    public void processTrade_publishesCandle_whenIntervalComplete() {
        long timestamp = System.currentTimeMillis() - (CANDLE_INTERVAL + 1000); // Past interval
        Trade trade = createTestTrade(timestamp);
        
        manager.processTrade(trade);
        
        verify(mockPublisher).publishCandle(any());
        assertThat(manager.getActiveBuilderCount()).isEqualTo(0);
    }

    @Test
    public void handleThinlyTradedMarkets_generatesEmptyCandles() {
        when(mockPriceTracker.getLastPrice(TEST_PAIR)).thenReturn(100.0);
        
        manager.handleThinlyTradedMarkets(ImmutableList.of(TEST_PAIR));
        
        verify(mockPublisher).publishCandle(argThat(candle -> 
            candle.getVolume() == 0.0 && candle.getOpen() == 100.0
        ));
    }

    @Test
    public void handleThinlyTradedMarkets_skipsWhenNoLastPrice() {
        when(mockPriceTracker.getLastPrice(TEST_PAIR)).thenReturn(Double.NaN);
        
        manager.handleThinlyTradedMarkets(ImmutableList.of(TEST_PAIR));
        
        verify(mockPublisher, never()).publishCandle(any());
    }

    private Trade createTestTrade(long timestamp) {
        return Trade.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair(TEST_PAIR)
            .setPrice(100.0)
            .setVolume(1.0)
            .setTradeId("test-" + System.nanoTime())
            .build();
    }
}
