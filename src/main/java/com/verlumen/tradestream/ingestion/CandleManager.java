package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Trade;

import java.util.List;

public interface CandleManager {
    void processTrade(Trade trade);

    void handleThinlyTradedMarkets(List<CurrencyPair> currencyPairs);

    int getActiveBuilderCount();

    interface Factory {
        CandleManager create(long candleIntervalMillis, CandlePublisher candlePublisher);
    }
}
