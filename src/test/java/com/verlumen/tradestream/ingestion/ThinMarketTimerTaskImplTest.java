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
import org.junit.After;
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
    private static final CurrencyPairMetadata AAA_BBB = CurrencyPairMetadata.create(new CurrencyPair("AAA", "BBB"), 123L);
    private static final CurrencyPairMetadata CCC_DDD = CurrencyPairMetadata.create(new CurrencyPair("CCC", "DDD"), 234L);
    private static final CurrencyPairMetadata EEE_FFF = CurrencyPairMetadata.create(new CurrencyPair("EEE", "FFF"), 345L);
    private static final CurrencyPairMetadata BTC_USD = CurrencyPairMetadata.create(new CurrencyPair("BTC", "USD"), 456L);
    private static final CurrencyPairMetadata ETH_EUR = CurrencyPairMetadata.create(new CurrencyPair("ETH", "EUR"), 567L);

    @Mock @Bind private CandleManager candleManager;
    @Bind private Provider<CurrencyPairSupply> currencyPairSupplyProvider;
    @Inject private ThinMarketTimerTaskImpl thinMarketTimerTask;
    
    @Before
    public void setUp() {
        this.currencyPairSupplyProvider = CURRENCY_PAIR_SUPPLY::get;
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(ImmutableList.of()));
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @After
    public void tearDown() {
        CURRENCY_PAIR_SUPPLY.set(null);
    }

    @Test
    public void run_withValidCurrencyPairs_callsHandleThinlyTradedMarketsWithCorrectList() {
        // Arrange
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of(BTC_USD, ETH_EUR);
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));

        // Act
        thinMarketTimerTask.run();

        // Assert
        ImmutableList<String> expected =
            ImmutableList.of(BTC_USD.currencyPair().toString(), ETH_EUR.currencyPair().toString());
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
        ImmutableList<CurrencyPairMetadata> metadataList = ImmutableList.of(AAA_BBB, CCC_DDD, EEE_FFF);
        CURRENCY_PAIR_SUPPLY.set(CurrencyPairSupply.create(metadataList));
        ImmutableList<String> expected = ImmutableList.of(
            AAA_BBB.currencyPair().toString(),
            CCC_DDD.currencyPair().toString(),
            EEE_FFF.currencyPair().toString());

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
        ImmutableList<String> expected =
            ImmutableList.of(BTC_USD.currencyPair().toString(), BTC_USD.currencyPair().toString());
        verify(candleManager).handleThinlyTradedMarkets(expected);
    }
}
