package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Trade;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

class TradeProcessor {
    private final Set<CandleKey> processedTrades = ConcurrentHashMap.newKeySet();
    private final long candleIntervalMillis;

    TradeProcessor(long candleIntervalMillis) {
        this.candleIntervalMillis = candleIntervalMillis;
    }

    public boolean isProcessed(Trade trade) {
        CandleKey key = new CandleKey(trade.getTradeId(), getMinuteTimestamp(trade.getTimestamp()));
        return !processedTrades.add(key);
    }

    public long getMinuteTimestamp(long timestamp) {
        return (timestamp / candleIntervalMillis) * candleIntervalMillis;
    }
}
