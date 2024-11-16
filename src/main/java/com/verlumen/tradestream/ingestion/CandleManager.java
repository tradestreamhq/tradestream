package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Trade;
import marketdata.Marketdata.Candle;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

interface CandleManager {
    void processTrade(Trade trade);

    void handleThinlyTradedMarkets(List<String> currencyPairs);
}
