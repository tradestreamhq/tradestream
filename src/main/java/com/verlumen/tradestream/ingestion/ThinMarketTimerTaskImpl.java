package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;

final class ThinMarketTimerTaskImpl extends ThinMarketTimerTask {
  private final CandleManager candleManager;
  private final CurrencyPairSupplier currencyPairSupplier;

  @Inject
  ThinMarketTimerTaskImpl (CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
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
      candleManager.handleThinlyTradedMarkets(currencyPairs);
  }
}
