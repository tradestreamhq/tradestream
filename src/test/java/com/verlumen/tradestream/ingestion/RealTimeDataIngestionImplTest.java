package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static com.google.common.truth.Truth.assertWithMessage;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Provides;
import com.google.inject.Provider;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Trade;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.disposables.Disposable;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.knowm.xchange.currency.CurrencyPair;
import org.knowm.xchange.dto.marketdata.Trade as XChangeTrade;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public final class RealTimeDataIngestionImplTest {
  @Rule public final MockitoRule mockitoRule = MockitoJUnit.rule();

  private static final CurrencyPair CURRENCY_PAIR = new CurrencyPair("BTC", "USD");
  private static final String PAIR_STRING = CURRENCY_PAIR.toString();
  private static final long TIMESTAMP = 12345L;

  @Mock @Bind private CandleManager mockCandleManager;
  @Mock @Bind private CandlePublisher mockCandlePublisher;
  @Mock @Bind private CurrencyPairSupplier mockCurrencyPairSupplier;
  @Mock @Bind private StreamingExchange mockExchange;
  @Mock @Bind private ThinMarketTimer mockThinMarketTimer;
  @Bind @Mock private TradeProcessor tradeProcessor;
  @Mock private StreamingMarketDataService mockMarketDataService;
  @Mock private Observable<XChangeTrade> mockTradeObservable;
  @Bind @Mock private Provider<ThinMarketTimer> mockThinMarketTimerProvider;

  @Inject private RealTimeDataIngestionImpl realTimeDataIngestion;
  private final List<Disposable> subscriptions = new java.util.ArrayList<>();

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void start_connectsToExchange() {
    // Arrange
    when(mockThinMarketTimerProvider.get()).thenReturn(mockThinMarketTimer);
    when(mockExchange.getStreamingMarketDataService()).thenReturn(mockMarketDataService);
    when(mockMarketDataService.getTrades(any())).thenReturn(mockTradeObservable);
    doReturn(mockTradeObservable)
        .when(mockMarketDataService)
        .getTrades(any(CurrencyPair.class));

    // Act
    realTimeDataIngestion.start();

    // Assert
    verify(mockExchange).connect();
  }

  @Test
@Test
public void start_subscribesToTradeStreams() {
    // Arrange
    when(mockCurrencyPairSupplier.currencyPairs()).thenReturn(ImmutableList.of(CURRENCY_PAIR));
    when(mockExchange.getStreamingMarketDataService()).thenReturn(mockMarketDataService);
    when(mockMarketDataService.getTrades(CURRENCY_PAIR)).thenReturn(mockTradeObservable);

    // Act
    realTimeDataIngestion.start();

    // Assert
    verify(mockMarketDataService).getTrades(CURRENCY_PAIR);
}

  @Test
  public void start_startsThinMarketTimer() {
    realTimeDataIngestion.start();
    verify(mockThinMarketTimer).start();
  }

  @Test
  public void shutdown_disposesSubscriptions() {
    Disposable mockDisposable = mock(Disposable.class);
    subscriptions.add(mockDisposable);
    realTimeDataIngestion.shutdown();
    verify(mockDisposable).dispose();
  }

  @Test
  public void shutdown_stopsThinMarketTimer() {
    realTimeDataIngestion.shutdown();
    verify(mockThinMarketTimer).stop();
  }

  @Test
  public void shutdown_disconnectsFromExchange() {
    realTimeDataIngestion.shutdown();
    verify(mockExchange).disconnect();
  }

  @Test
  public void shutdown_closesCandlePublisher() {
    realTimeDataIngestion.shutdown();
    verify(mockCandlePublisher).close();
  }
}
