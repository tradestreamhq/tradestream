package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Trade;

import java.util.List;

public interface CandleManager {
    void processTrade(Trade trade);

    void handleThinlyTradedMarkets(List<String> currencyPairs);

    int getActiveBuilderCount()

    interface Factory {
        CandleManager create(long candleIntervalMillis, String topic);
    }
}
