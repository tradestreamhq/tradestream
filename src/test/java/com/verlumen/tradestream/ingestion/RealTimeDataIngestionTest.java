package com.verlumen.tradestream.ingestion;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.subjects.PublishSubject;
import marketdata.Marketdata.Trade;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.knowm.xchange.dto.marketdata.Trades;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.math.BigDecimal;
import java.util.Date;

@RunWith(TestParameterInjector.class)
public class RealTimeDataIngestionIntegrationTest {
    private static final String TEST_PAIR = "BTC/USD";
    private static final List<String> TEST_PAIRS = ImmutableList.of(TEST_PAIR);

    @Mock private StreamingExchange mockExchange;
    @Mock private StreamingMarketDataService mockMarketDataService;
    @Mock private CandleManager mockCandleManager;
    @Mock private TradeProcessor mockTradeProcessor;
    @Mock private CandlePublisher mockPublisher;
    
    private RealTimeDataIngestion dataIngestion;
    private PublishSubject<org.knowm.xchange.dto.marketdata.Trade> tradeSubject;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        tradeSubject = PublishSubject.create();

        when(mockExchange.getStreamingMarketDataService()).thenReturn(mockMarketDataService);
        when(mockExchange.connect()).thenReturn(Completable.complete());
        when(mockExchange.disconnect()).thenReturn(Completable.complete());
        when(mockExchange.getExchangeSpecification().getExchangeName()).thenReturn("TestExchange");
        when(mockMarketDataService.getTrades(any())).thenReturn(tradeSubject);

        dataIngestion = new RealTimeDataIngestion(
            mockExchange,
            mockMarketDataService,
            TEST_PAIRS,
            mockCandleManager,
            mockTradeProcessor,
            mockPublisher
        );
    }

    @Test
    public void fullTradeFlow_processesTradeCorrectly() {
        // Arrange
        when(mockTradeProcessor.isProcessed(any())).thenReturn(false);
        org.knowm.xchange.dto.marketdata.Trade xchangeTrade = new org.knowm.xchange.dto.marketdata.Trade.Builder()
            .price(new BigDecimal("50000.0"))
            .originalAmount(new BigDecimal("1.0"))
            .timestamp(new Date())
            .id("test-trade")
            .build();

        // Act
        dataIngestion.start();
        tradeSubject.onNext(xchangeTrade);

        // Assert
        verify(mockTradeProcessor).isProcessed(any(Trade.class));
        verify(mockCandleManager).processTrade(any(Trade.class));
    }

    @Test
    public void duplicateTrade_isNotProcessed() {
        // Arrange
        when(mockTradeProcessor.isProcessed(any())).thenReturn(true);
        org.knowm.xchange.dto.marketdata.Trade xchangeTrade = new org.knowm.xchange.dto.marketdata.Trade.Builder()
            .price(new BigDecimal("50000.0"))
            .originalAmount(new BigDecimal("1.0"))
            .timestamp(new Date())
            .id("test-trade")
            .build();

        // Act
        dataIngestion.start();
        tradeSubject.onNext(xchangeTrade);

        // Assert
        verify(mockTradeProcessor).isProcessed(any(Trade.class));
        verify(mockCandleManager, never()).processTrade(any(Trade.class));
    }

    @Test
    public void shutdown_cleansUpResources() {
        // Act
        dataIngestion.start();
        dataIngestion.shutdown();

        // Assert
        verify(mockExchange).disconnect();
        verify(mockPublisher).close();
    }
}
