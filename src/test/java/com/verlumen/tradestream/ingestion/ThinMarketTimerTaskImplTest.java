package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.*;
import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.knowm.xchange.currency.CurrencyPair;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;


public class ThinMarketTimerTaskImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    @Mock @Bind private CandleManager candleManager;
    @Mock @Bind private CurrencyPairSupplier currencyPairSupplier;
    @Inject private ThinMarketTimerTaskImpl thinMarketTimerTask;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void run_withValidCurrencyPairs_callsHandleThinlyTradedMarketsWithCorrectList() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC", "USD");
        CurrencyPair ethEur = new CurrencyPair("ETH", "EUR");
        ImmutableList<CurrencyPair> currencyPairs = ImmutableList.of(btcUsd, ethEur);
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(btcUsd.toString(), ethEur.toString());
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withEmptyCurrencyPairs_callsHandleThinlyTradedMarketsWithEmptyList() {
        // Arrange
        when(currencyPairSupplier.currencyPairs()).thenReturn(ImmutableList.of());

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of();
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withNullCurrencyPairs_throwsNullPointerException() {
        // Arrange
        when(currencyPairSupplier.currencyPairs()).thenReturn(null);

        // Act & Assert
        try {
            thinMarketTimerTask.run();
            fail("Expected NullPointerException");
        } catch (NullPointerException e) {
            // Expected exception
        }
    }

    @Test
    public void run_withNullElementInCurrencyPairs_throwsNullPointerException() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC", "USD");
        ImmutableList<CurrencyPair> currencyPairs = ImmutableList.of(btcUsd, null);
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);

        // Act & Assert
        try {
            thinMarketTimerTask.run();
            fail("Expected NullPointerException");
        } catch (NullPointerException e) {
            // Expected exception
        }
    }

    @Test
    public void run_currencyPairToStringReturnsNull_handlesNullInResultList() {
        // Arrange
        CurrencyPair mockCurrencyPair = mock(CurrencyPair.class);
        when(mockCurrencyPair.toString()).thenReturn(null);
        ImmutableList<CurrencyPair> currencyPairs = ImmutableList.of(mockCurrencyPair);
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of((String) null);
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_handleThinlyTradedMarketsThrowsException_exceptionIsPropagated() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC", "USD");
        ImmutableList<CurrencyPair> currencyPairs = ImmutableList.of(btcUsd);
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);
        doThrow(new RuntimeException("Test exception")).when(candleManager).handleThinlyTradedMarkets(any());

        // Act & Assert
        try {
            thinMarketTimerTask.run();
            fail("Expected RuntimeException");
        } catch (RuntimeException e) {
            assertEquals("Test exception", e.getMessage());
        }
    }

    @Test
    public void run_currencyPairsOrderIsPreserved() {
        // Arrange
        CurrencyPair pair1 = new CurrencyPair("AAA", "BBB");
        CurrencyPair pair2 = new CurrencyPair("CCC", "DDD");
        CurrencyPair pair3 = new CurrencyPair("EEE", "FFF");
        ImmutableList<CurrencyPair> currencyPairs =ImmutableList.of(pair1, pair2, pair3);
        ImmutableList<String> expected = ImmutableList.of(pair1.toString(), pair2.toString(), pair3.toString());
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withDuplicateCurrencyPairs_duplicatesAreIncludedInResultList() {
        // Arrange
        CurrencyPair btcUsd = new CurrencyPair("BTC", "USD");
        ImmutableList<CurrencyPair> currencyPairs = ImmutableList.of(btcUsd, btcUsd);
        when(currencyPairSupplier.currencyPairs()).thenReturn(currencyPairs);

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(btcUsd.toString(), btcUsd.toString());
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }
}
