package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;

final class ThinMarketTimerTaskImpl extends ThinMarketTimerTask {
  private final CandleManager candleManager;
  private final CurrencyPairSupplier currencyPairSupply;

  @Inject
  ThinMarketTimerTaskImpl (CandleManager candleManager, CurrencyPairSupply currencyPairSupply) {
      this.candleManager = candleManager;
      this.currencyPairSupply = currencyPairSupply;
  }

  @Override
  public void run() {
      ImmutableList<String> currencyPairs =
        currencyPairSupply
        .currencyPairs()
        .stream()
        .map(Object::toString)
        .collect(toImmutableList());
      candleManager.handleThinlyTradedMarkets(currencyPairs);
  }
}
