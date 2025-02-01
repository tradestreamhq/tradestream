package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Trade;
import com.verlumen.tradestream.marketdata.TradePublisher;
import java.util.function.Consumer;
import java.util.stream.Stream;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class RealTimeDataIngestionImplTest {
    @Rule public final MockitoRule mockito = MockitoJUnit.rule();

    private static final ImmutableList<CurrencyPair> SUPPORTED_CURRENCY_PAIRS = 
        Stream.of("BTC/USD", "ETH/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
    private static final ImmutableList<CurrencyPair> UNSUPPORTED_CURRENCY_PAIRS = 
        Stream.of("ETH/USD", "DOGE/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
    private static final ImmutableList<CurrencyPair> TEST_CURRENCY_PAIRS = 
        ImmutableList.<CurrencyPair>builder()
            .addAll(SUPPORTED_CURRENCY_PAIRS)
            .addAll(UNSUPPORTED_CURRENCY_PAIRS)
            .build();
    private static final String TEST_EXCHANGE = "test-exchange";

    @Mock @Bind private CandleManager mockCandleManager;
    @Mock @Bind private CandlePublisher mockCandlePublisher;
    @Mock @Bind private CurrencyPairSupply mockCurrencyPairSupply;
    @Mock @Bind private ExchangeStreamingClient mockExchangeClient;
    @Mock @Bind private ThinMarketTimer mockThinMarketTimer;
    @Mock @Bind private TradeProcessor mockTradeProcessor;
    @Mock @Bind private TradePublisher tradePublisher;

    @Inject private RealTimeDataIngestionImpl realTimeDataIngestion;

    @Before
    public void setUp() {
        when(mockCurrencyPairSupply.currencyPairs()).thenReturn(TEST_CURRENCY_PAIRS);
        when(mockExchangeClient.getExchangeName()).thenReturn(TEST_EXCHANGE);
        when(mockExchangeClient.supportedCurrencyPairs()).thenReturn(SUPPORTED_CURRENCY_PAIRS);

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void start_initiatesStreaming() {
        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockExchangeClient).startStreaming(eq(SUPPORTED_CURRENCY_PAIRS), any(Consumer.class));
    }

    @Test
    public void start_startsThinMarketTimer() {
        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockThinMarketTimer).start();
    }

    @Test
    public void shutdown_stopsStreamingAndTimer() {
        // Arrange
        realTimeDataIngestion.start();

        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockExchangeClient).stopStreaming();
        verify(mockThinMarketTimer).stop();
        verify(mockCandlePublisher).close();
    }

    @Test
    public void shutdown_handlesCandlePublisherException() {
        // Arrange
        doThrow(new RuntimeException("Test exception"))
            .when(mockCandlePublisher)
            .close();

        // Act - Should not throw
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockExchangeClient).stopStreaming();
        verify(mockThinMarketTimer).stop();
    }

    @Test
    public void processTrade_handlesNewTrade() {
        // Arrange
        ArgumentCaptor<Consumer<Trade>> handlerCaptor = 
            ArgumentCaptor.forClass(Consumer.class);
        
        realTimeDataIngestion.start();
        verify(mockExchangeClient).startStreaming(any(), handlerCaptor.capture());
        
        Trade trade = Trade.newBuilder()
            .setTradeId("test-trade")
            .setCurrencyPair("BTC/USD")
            .setPrice(50000.0)
            .setVolume(1.0)
            .build();
        
        when(mockTradeProcessor.isProcessed(trade)).thenReturn(false);

        // Act
        handlerCaptor.getValue().accept(trade);

        // Assert
        verify(mockCandleManager).processTrade(trade);
    }

    @Test
    public void processTrade_skipsDuplicateTrade() {
        // Arrange
        ArgumentCaptor<Consumer<Trade>> handlerCaptor = 
            ArgumentCaptor.forClass(Consumer.class);
        
        realTimeDataIngestion.start();
        verify(mockExchangeClient).startStreaming(any(), handlerCaptor.capture());
        
        Trade trade = Trade.newBuilder()
            .setTradeId("test-trade")
            .setCurrencyPair("BTC/USD")
            .setPrice(50000.0)
            .setVolume(1.0)
            .build();
        
        when(mockTradeProcessor.isProcessed(trade)).thenReturn(true);

        // Act
        handlerCaptor.getValue().accept(trade);

        // Assert
        verify(mockCandleManager, never()).processTrade(trade);
    }

    @Test
    public void lifecycle_properStartupShutdownSequence() {
        // Act - Start
        realTimeDataIngestion.start();

        // Assert - Started correctly
        verify(mockExchangeClient).startStreaming(any(), any());
        verify(mockThinMarketTimer).start();

        // Act - Shutdown
        realTimeDataIngestion.shutdown();

        // Assert - Shutdown correctly
        verify(mockExchangeClient).stopStreaming();
        verify(mockThinMarketTimer).stop();
        verify(mockCandlePublisher).close();
    }

    @Test
    public void processTrade_handlesTradeProcessorException() {
        // Arrange
        ArgumentCaptor<Consumer<Trade>> handlerCaptor = 
            ArgumentCaptor.forClass(Consumer.class);
        
        realTimeDataIngestion.start();
        verify(mockExchangeClient).startStreaming(any(), handlerCaptor.capture());
        
        Trade trade = Trade.newBuilder()
            .setTradeId("test-trade")
            .setCurrencyPair("BTC/USD")
            .build();
        
        when(mockTradeProcessor.isProcessed(trade))
            .thenThrow(new RuntimeException("Test exception"));

        // Act - Should not throw
        handlerCaptor.getValue().accept(trade);

        // Assert
        verify(mockCandleManager, never()).processTrade(any());
    }
}
