package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.verlumen.tradestream.marketdata.Trade;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

@AutoValue
abstract class TradeProcessor {
    static TradeProcessor create(long candleIntervalMillis) {
        return new AutoValue_TradeProcessor(candleIntervalMillis, ConcurrentHashMap.newKeySet());
    }
    
    abstract long candleIntervalMillis();
    abstract Set<CandleKey> processedTrades();

    boolean isProcessed(Trade trade) {
        CandleKey key = CandleKey.create(trade.getTradeId(), getMinuteTimestamp(trade.getTimestamp()));
        return !processedTrades().add(key);
    }

    long getMinuteTimestamp(long timestamp) {
        return (timestamp / candleIntervalMillis()) * candleIntervalMillis();
    }

    @AutoValue
    abstract static class CandleKey {
        private static CandleKey create(String tradeId, long minuteTimestamp) {
            return new AutoValue_TradeProcessor_CandleKey(tradeId, minuteTimestamp);
        }
    
        abstract String tradeId();
        abstract long minuteTimestamp();
    }
}
