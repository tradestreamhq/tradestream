package com.verlumen.tradestream.ingestion;

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
import java.lang.reflect.Field;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
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
            .collect(ImmutableList.toImmutableList());
    private static final ImmutableList<CurrencyPair> UNSUPPORTED_CURRENCY_PAIRS = 
        Stream.of("ETH/USD", "DOGE/USD")
            .map(CurrencyPair::fromSymbol)
            .collect(ImmutableList.toImmutableList());
    private static final ImmutableList<CurrencyPair> TEST_CURRENCY_PAIRS = 
        ImmutableList.<CurrencyPair>builder()
            .addAll(SUPPORTED_CURRENCY_PAIRS)
            .addAll(UNSUPPORTED_CURRENCY_PAIRS)
            .build();
    private static final String TEST_EXCHANGE = "test-exchange";

    @Mock @Bind private CurrencyPairSupply mockCurrencyPairSupply;
    @Mock @Bind private ExchangeStreamingClient mockExchangeClient;
    @Mock @Bind private TradePublisher mockTradePublisher;

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
    public void shutdown_stopsStreamingAndTimer() {
        // Arrange
        realTimeDataIngestion.start();

        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockExchangeClient).stopStreaming();
        verify(mockTradePublisher).close();
    }

    @Test
    public void shutdown_handlesTradePublisherException() {
        // Arrange
        doThrow(new RuntimeException("Test exception"))
            .when(mockTradePublisher)
            .close();

        // Act - Should not throw
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockExchangeClient).stopStreaming();
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
        
        // Act
        handlerCaptor.getValue().accept(trade);

        // Assert
        verify(mockTradePublisher).publishTrade(trade);
    }

    @Test
    public void lifecycle_properStartupShutdownSequence() {
        // Act - Start
        realTimeDataIngestion.start();

        // Assert - Started correctly
        verify(mockExchangeClient).startStreaming(any(), any());

        // Act - Shutdown
        realTimeDataIngestion.shutdown();

        // Assert - Shutdown correctly
        verify(mockExchangeClient).stopStreaming();
        verify(mockTradePublisher).close();
    }

    @Test
    public void backgroundThread_runsUntilShutdown() throws Exception {
        // Act - Start the ingestion service.
        realTimeDataIngestion.start();

        // Use reflection to get the private 'tradePublisherExecutor' field.
        Field executorField = RealTimeDataIngestionImpl.class.getDeclaredField("tradePublisherExecutor");
        executorField.setAccessible(true);
        ExecutorService executorService = (ExecutorService) executorField.get(realTimeDataIngestion);

        // Assert that the executor is not null and is still running.
        assertThat(executorService).isNotNull();
        assertThat(executorService.isShutdown()).isFalse();

        // Call shutdown on the ingestion service.
        realTimeDataIngestion.shutdown();

        // Wait a bit to allow shutdown to complete.
        boolean terminated = executorService.awaitTermination(5, TimeUnit.SECONDS);
        assertThat(terminated).isTrue();
        assertThat(executorService.isShutdown()).isTrue();
    }
}
