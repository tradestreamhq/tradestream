package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.instruments.CurrencyPair;

final class ThinMarketTimerTaskImpl extends ThinMarketTimerTask {
  private final Provider<CandleManager> candleManager;
  private final Provider<CurrencyPairSupply> currencyPairSupply;

  @Inject
  ThinMarketTimerTaskImpl(
    Provider<CandleManager candleManager, Provider<CurrencyPairSupply> currencyPairSupply) {
      this.candleManager = candleManager;
      this.currencyPairSupply = currencyPairSupply;
  }

  @Override
  public void run() {
      candleManager
        .get()
        .handleThinlyTradedMarkets(currencyPairSupply.get().currencyPairs());
  }
}
