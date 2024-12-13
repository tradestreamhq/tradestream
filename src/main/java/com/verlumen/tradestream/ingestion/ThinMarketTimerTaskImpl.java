package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.instruments.CurrencyPair;

final class ThinMarketTimerTaskImpl extends ThinMarketTimerTask {
  private final CandleManager candleManager;
  private final CurrencyPairSupply currencyPairSupply;

  @Inject
  ThinMarketTimerTaskImpl(CandleManager candleManager, CurrencyPairSupply currencyPairSupply) {
    this.candleManager = candleManager;
    this.currencyPairSupply = currencyPairSupply;
  }

  @Override
  public void run() {
    ImmutableList<CurrencyPair> currencyPairs = currencyPairSupply.currencyPairs();
    candleManager.handleThinlyTradedMarkets(currencyPairs);
  }
}
