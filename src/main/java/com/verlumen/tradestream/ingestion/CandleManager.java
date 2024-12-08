package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Trade;

public interface CandleManager {
    void processTrade(Trade trade);

    void handleThinlyTradedMarkets(ImmutableList<CurrencyPair> currencyPairs);

    int getActiveBuilderCount();

    interface Factory {
        CandleManager create(long candleIntervalMillis, CandlePublisher candlePublisher);
    }
}
