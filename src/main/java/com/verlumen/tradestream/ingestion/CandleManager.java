package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Trade;

import java.util.List;

interface CandleManager {
    void processTrade(Trade trade);

    void handleThinlyTradedMarkets(List<String> currencyPairs);
}
