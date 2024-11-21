package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;

final class ThinMarketTimerTask extends TimerTask {
    static ThinMarketTimerTask create(CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
        return new AutoValue_RealTimeDataIngestion_ThinMarketTimerTask(candleManager, currencyPairSupplier);
    }

    abstract CandleManager candleManager();

    abstract CurrencyPairSupplier currencyPairSupplier();

    @Override
    public void run() {
        ImmutableList<String> currencyPairs =
          currencyPairSupplier()
          .currencyPairs()
          .stream()
          .map(Object::toString)
          .collect(toImmutableList());
        candleManager().handleThinlyTradedMarkets(currencyPairs);
    }
}
