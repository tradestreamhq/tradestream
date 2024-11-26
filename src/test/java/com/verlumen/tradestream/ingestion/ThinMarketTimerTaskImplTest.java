package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.*;
import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Provider;
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

import java.util.concurrent.atomic.AtomicReference;

public class ThinMarketTimerTaskImplTest {
    @Rule public MockitoRule mocks = MockitoJUnit.rule();
    private static final AtomicReference<CurrencyPairSupply> CURRENCY_PAIR_SUPPLY = new AtomicReference<>();
    private static final CurrencyPairMetadata BTC_USD = CurrencyPairMetadata.create(new CurrencyPair("BTC", "USD"), 123L);
    private static final CurrencyPairMetadata ETH_EUR = CurrencyPairMetadata.create(new CurrencyPair("ETH", "EUR"), 456L);

    @Mock @Bind private CandleManager candleManager;
    @Bind private Provider<CurrencyPairSupply> currencyPairSupply;
    @Inject private ThinMarketTimerTaskImpl thinMarketTimerTask;

    @Before
    public void setUp() {
        this.currencyPairSupply = CURRENCY_PAIR_SUPPLY::get;
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void run_withValidCurrencyPairs_callsHandleThinlyTradedMarketsWithCorrectList() {
        // Arrange
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of(BTC_USD, ETH_EUR);
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(btcUsd.toString(), ethEur.toString());
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withEmptyCurrencyPairs_callsHandleThinlyTradedMarketsWithEmptyList() {
        // Arrange
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of();
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of();
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_handleThinlyTradedMarketsThrowsException_exceptionIsPropagated() {
        // Arrange
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of(BTC_USD);
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));
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

        // Act
        thinMarketTimerTask.run();

        // Assert
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }

    @Test
    public void run_withDuplicateCurrencyPairs_duplicatesAreIncludedInResultList() {
        // Arrange
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of(BTC_USD, BTC_USD);
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected = ImmutableList.of(btcUsd.toString(), btcUsd.toString());
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }
}
