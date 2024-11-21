package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;

final class ThinMarketTimerTaskImpl extends TimerTask {
    private final CandleManager candleManager;
    private final CurrencyPairSupplier currencyPairSupplier;

    ThinMarketTimerTask (CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
        this.candleManager = candleManager;
        this.currencyPairSupplier = currencyPairSupplier;
    }

    @Override
    public void run() {
        ImmutableList<String> currencyPairs =
          currencyPairSupplier
          .currencyPairs()
          .stream()
          .map(Object::toString)
          .collect(toImmutableList());
        candleManager().handleThinlyTradedMarkets(currencyPairs);
    }
}
