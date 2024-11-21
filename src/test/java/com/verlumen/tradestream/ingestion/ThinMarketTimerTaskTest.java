package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.Before;
import org.junit.Test;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class ThinMarketTimerTaskTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private CandleManager candleManager;
    @Mock @Bind private CurrencyPairSupplier currencyPairSupplier;
    @Inject private ThinMarketTimerTask thinMarketTimerTask;

    @Before
    public void setUp() {
        Guice.createInjector
    }

    @Test
    public void run_withValidCurrencyPairs_callsHandleThinlyTradedMarkets() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC/USD");
        CurrencyPair ethUsd = new CurrencyPair("ETH/USD");
        when(currencyPairSupplier.currencyPairs()).thenReturn(Arrays.asList(btcUsd, ethUsd));

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of("BTC/USD", "ETH/USD"));
    }

    @Test
    public void run_withEmptyCurrencyPairs_callsHandleThinlyTradedMarketsWithEmptyList() {
        // Arrange
        when(currencyPairSupplier.currencyPairs()).thenReturn(Collections.emptyList());

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of());
    }

    @Test
    public void run_withNullCurrencyPairs_throwsNullPointerException() {
        // Arrange
        when(currencyPairSupplier.currencyPairs()).thenReturn(null);

        // Act / Assert
        assertThrows(NullPointerException.class, thinMarketTimerTask::run);
    }

    @Test(expected = NullPointerException.class)
    public void run_withNullElementInCurrencyPairs_throwsNullPointerException() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC/USD");
        when(currencyPairSupplier.currencyPairs()).thenReturn(Arrays.asList(btcUsd, null));

        // Act / Assert
        assertThrows(NullPointerException.class, thinMarketTimerTask::run);
    }

    @Test
    public void run_currencyPairsOrderIsPreserved() {
        // Arrange
        CurrencyPair firstPair = new CurrencyPair("FIRST/PAIR");
        CurrencyPair secondPair = new CurrencyPair("SECOND/PAIR");
        CurrencyPair thirdPair = new CurrencyPair("THIRD/PAIR");
        when(currencyPairSupplier.currencyPairs()).thenReturn(Arrays.asList(firstPair, secondPair, thirdPair));

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of("FIRST/PAIR", "SECOND/PAIR", "THIRD/PAIR"));
    }

    @Test
    public void run_withDuplicateCurrencyPairs_callsHandleThinlyTradedMarketsWithDuplicates() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC/USD");
        when(currencyPairSupplier.currencyPairs()).thenReturn(Arrays.asList(btcUsd, btcUsd));

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of("BTC/USD", "BTC/USD"));
    }

    @Test(expected = RuntimeException.class)
    public void run_whenHandleThinlyTradedMarketsThrows_exceptionIsPropagated() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC/USD");
        when(currencyPairSupplier.currencyPairs()).thenReturn(Collections.singletonList(btcUsd));
        doThrow(new RuntimeException()).when(candleManager).handleThinlyTradedMarkets(any());

        // Act
        thinMarketTimerTask.run();

        // Act / Assert
        assertThrows(RuntimeException.class, thinMarketTimerTask::run);
    }

    @Test
    public void run_withCurrencyPairToStringReturningNull_callsHandleThinlyTradedMarketsWithNullElement() {
        // Arrange
        CurrencyPair currencyPair = mock(CurrencyPair.class);
        when(currencyPair.toString()).thenReturn(null);
        when(currencyPairSupplier.currencyPairs()).thenReturn(Collections.singletonList(currencyPair));

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of((String) null));
    }
}
