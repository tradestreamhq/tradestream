package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.*;
import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.knowm.xchange.currency.CurrencyPair;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class ThinMarketTimerTaskImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();

    private static final CurrencyPairMetadata BTC_USD = 
        CurrencyPairMetadata.create("BTC/USD", 456L);
    private static final CurrencyPairMetadata ETH_EUR = 
        CurrencyPairMetadata.create("ETH/EUR", 567L);

    @Mock @Bind private CandleManager candleManager;
    @Mock @Bind private CurrencyPairSupply currencyPairSupply;
    @Inject private ThinMarketTimerTaskImpl timerTask;

    @Before
    public void setUp() {
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
        // Default to empty list of currency pairs
        when(currencyPairSupply.currencyPairs())
            .thenReturn(ImmutableList.of());
    }

    @Test
    public void run_withValidCurrencyPairs_callsHandleThinlyTradedMarketsWithCorrectList() {
        // Arrange
        ImmutableList<CurrencyPair> pairs = ImmutableList.of(
            BTC_USD.currencyPair(), 
            ETH_EUR.currencyPair()
        );
        when(currencyPairSupply.currencyPairs()).thenReturn(pairs);

        // Act
        timerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(
            BTC_USD.currencyPair().toString(), 
            ETH_EUR.currencyPair().toString()
        );
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withEmptyCurrencyPairs_callsHandleThinlyTradedMarketsWithEmptyList() {
        // Act
        timerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(ImmutableList.of());
    }

    @Test
    public void run_handleThinlyTradedMarketsThrowsException_exceptionIsPropagated() {
        // Arrange
        when(currencyPairSupply.currencyPairs())
            .thenReturn(ImmutableList.of(BTC_USD.currencyPair()));
        doThrow(new RuntimeException("Test exception"))
            .when(candleManager)
            .handleThinlyTradedMarkets(any());

        // Act & Assert
        try {
            timerTask.run();
            fail("Expected RuntimeException");
        } catch (RuntimeException e) {
            assertEquals("Test exception", e.getMessage());
        }
    }

    @Test
    public void run_currencyPairsOrderIsPreserved() {
        // Arrange
        ImmutableList<CurrencyPair> pairs = ImmutableList.of(
            new CurrencyPair("AAA", "BBB"),
            new CurrencyPair("CCC", "DDD"),
            new CurrencyPair("EEE", "FFF")
        );
        when(currencyPairSupply.currencyPairs()).thenReturn(pairs);

        // Act
        timerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(
            "AAA/BBB", "CCC/DDD", "EEE/FFF"
        );
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test 
    public void run_withDuplicateCurrencyPairs_duplicatesAreIncludedInResultList() {
        // Arrange
        ImmutableList<CurrencyPair> pairs = ImmutableList.of(
            BTC_USD.currencyPair(),
            BTC_USD.currencyPair()
        );
        when(currencyPairSupply.currencyPairs()).thenReturn(pairs);

        // Act
        timerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(
            BTC_USD.currencyPair().toString(),
            BTC_USD.currencyPair().toString()
        );
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }
}
