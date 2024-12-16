package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class CandleManagerImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();
    
    private static final long CANDLE_INTERVAL = 60000L;
    private static final CurrencyPair TEST_PAIR = CurrencyPair.fromSymbol("BTC/USD");
    
    @Mock private CandlePublisher mockPublisher;
    @Mock @Bind private PriceTracker mockPriceTracker;
    @Inject private CandleManager.Factory factory;

    @Before
    public void setUp() {
        Guice
            .createInjector(
                BoundFieldModule.of(this), 
                new FactoryModuleBuilder()
                     .implement(CandleManager.class, CandleManagerImpl.class)
                     .build(CandleManager.Factory.class)
            )
            .injectMembers(this);        
    }

    @Test
    public void processTrade_createsNewBuilder() {
        // Arrange
        long timestamp = System.currentTimeMillis();
        Trade trade = createTestTrade(timestamp);
        CandleManager manager = factory.create(CANDLE_INTERVAL, mockPublisher);

        // Act
        manager.processTrade(trade);

        // Assert
        assertThat(manager.getActiveBuilderCount()).isEqualTo(1);
    }

    @Test
    public void processTrade_updatesLastPrice() {
        // Arrange
        Trade trade = createTestTrade(System.currentTimeMillis());
        CandleManager manager = factory.create(CANDLE_INTERVAL, mockPublisher);

        // Act
        manager.processTrade(trade);

        // Assert
        verify(mockPriceTracker).updateLastPrice(TEST_PAIR, trade.getPrice());
    }

    @Test
    public void processTrade_publishesCandle_whenIntervalComplete() {
        // Arrange
        long timestamp = System.currentTimeMillis() - (CANDLE_INTERVAL + 1000); // Past interval
        Trade trade = createTestTrade(timestamp);
        CandleManager manager = factory.create(CANDLE_INTERVAL, mockPublisher);

        // Act
        manager.processTrade(trade);

        // Assert
        verify(mockPublisher).publishCandle(any());
        assertThat(manager.getActiveBuilderCount()).isEqualTo(0);
    }

    @Test
    public void handleThinlyTradedMarkets_generatesEmptyCandles() {
        // Arrange
        CandleManager manager = factory.create(CANDLE_INTERVAL, mockPublisher);
        when(mockPriceTracker.getLastPrice(TEST_PAIR)).thenReturn(100.0);

        // Act
        manager.handleThinlyTradedMarkets(ImmutableList.of(TEST_PAIR));

        // Assert
        verify(mockPublisher).publishCandle(argThat(candle -> 
            candle.getVolume() == 0.0 && candle.getOpen() == 100.0
        ));
    }

    @Test
    public void handleThinlyTradedMarkets_skipsWhenNoLastPrice() {
        // Arrange
        CandleManager manager = factory.create(CANDLE_INTERVAL, mockPublisher);

        when(mockPriceTracker.getLastPrice(TEST_PAIR)).thenReturn(Double.NaN);
        
        // Act
        manager.handleThinlyTradedMarkets(ImmutableList.of(TEST_PAIR));

        // Assert
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
