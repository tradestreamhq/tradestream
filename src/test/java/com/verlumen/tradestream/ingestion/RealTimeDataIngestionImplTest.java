package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import info.bitrich.xchangestream.core.ProductSubscription;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.core.Observable;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.knowm.xchange.currency.CurrencyPair;
import org.knowm.xchange.dto.marketdata.Trade;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public final class RealTimeDataIngestionImplTest {
    @Rule public final MockitoRule mockitoRule = MockitoJUnit.rule();

    private static final CurrencyPair CURRENCY_PAIR = new CurrencyPair("BTC", "USD");
    private static final String PAIR_STRING = CURRENCY_PAIR.toString();

    @Mock @Bind private CandleManager mockCandleManager;
    @Mock @Bind private CandlePublisher mockCandlePublisher;
    @Mock @Bind private CurrencyPairSupply mockCurrencyPairSupply;
    @Mock @Bind private StreamingExchange mockExchange;
    @Mock @Bind private ProductSubscription mockProductSubscription;
    @Mock @Bind private ThinMarketTimer mockThinMarketTimer;
    @Mock @Bind private TradeProcessor mockTradeProcessor;
    @Mock private StreamingMarketDataService mockMarketDataService;
    @Mock private Observable<Trade> mockTradeObservable;

    @Inject private RealTimeDataIngestionImpl realTimeDataIngestion;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
        
        // Setup basic mocking behavior
        when(mockExchange.getStreamingMarketDataService()).thenReturn(mockMarketDataService);
        when(mockMarketDataService.getTrades(any(CurrencyPair.class))).thenReturn(mockTradeObservable);
        when(mockExchange.connect(any(ProductSubscription.class))).thenReturn(Completable.complete());
        when(mockExchange.disconnect()).thenReturn(Completable.complete());
        when(mockCurrencyPairSupply.currencyPairs()).thenReturn(ImmutableList.of(CURRENCY_PAIR));
    }

    @Test
    public void start_connectsToExchange() {
        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockExchange).connect(any(ProductSubscription.class));
    }

    @Test
    public void start_subscribesToTradeStreams() {
        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockMarketDataService).getTrades(CURRENCY_PAIR);
    }

    @Test
    public void start_startsThinMarketTimer() {
        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockThinMarketTimer).start();
    }

    @Test
    public void shutdown_disconnectsFromExchange() {
        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockExchange).disconnect();
    }

    @Test
    public void shutdown_closesCandlePublisher() {
        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockCandlePublisher).close();
    }

    @Test
    public void shutdown_stopsThinMarketTimer() {
        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockThinMarketTimer).stop();
    }
}
