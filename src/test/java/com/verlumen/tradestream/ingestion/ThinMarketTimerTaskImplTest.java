package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.*;
import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.math.BigDecimal;

@RunWith(JUnit4.class)
public class ThinMarketTimerTaskImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();
    private static final BigDecimal BTC_USD_MARKET_CAP = BigDecimal.valueOf(456.78);
    private static final BigDecimal ETH_EUR_MARKET_CAP = BigDecimal.valueOf(567.89);
    private static final CurrencyPairMetadata BTC_USD = 
        CurrencyPairMetadata.create("BTC/USD", BTC_USD_MARKET_CAP);
    private static final CurrencyPairMetadata ETH_EUR = 
        CurrencyPairMetadata.create("ETH/EUR", ETH_EUR_MARKET_CAP);

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
        when(currencyPairSupply.metadataList())
            .thenReturn(ImmutableList.of(BTC_USD, ETH_EUR));

        // Act
        timerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(
            ImmutableList.of(
                BTC_USD.currencyPair(),
                ETH_EUR.currencyPair()
            ));
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
            CurrencyPair.fromSymbol("AAA/BBB"),
            CurrencyPair.fromSymbol("CCC/DDD"),
            CurrencyPair.fromSymbol("EEE/FFF")
        );
        when(currencyPairSupply.currencyPairs()).thenReturn(pairs);

        // Act
        timerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(pairs);
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
