package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.flogger.FluentLogger;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Trade;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Processes incoming trades and maintains state to detect duplicates within candle intervals.
 * This class helps ensure data quality by preventing duplicate trades from affecting candle
 * generation while allowing the same trade ID to be reused across different time intervals.
 *
 * <p>Thread-safety: This class is thread-safe for concurrent access through its synchronized
 * collections and immutable state.
 */
@AutoValue
abstract class TradeProcessor {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    /**
     * Creates a new TradeProcessor for the specified candle interval.
     *
     * @param candleIntervalMillis The candle interval duration in milliseconds
     * @return A new TradeProcessor instance
     */
    static TradeProcessor create(long candleIntervalMillis) {
        logger.atInfo().log("Creating new TradeProcessor with candle interval: %d ms", 
            candleIntervalMillis);
        TradeProcessor processor = new AutoValue_TradeProcessor(
            candleIntervalMillis, 
            ConcurrentHashMap.newKeySet()
        );
        logger.atInfo().log("TradeProcessor created successfully");
        return processor;
    }
    
    /**
     * Returns the configured candle interval in milliseconds.
     */
    abstract long candleIntervalMillis();

    /**
     * Returns the set of processed trade keys, tracking trade IDs and their timestamps.
     */
    abstract Set<CandleKey> processedTrades();

    /**
     * Checks if a trade has already been processed within its candle interval.
     * A trade is considered a duplicate if another trade with the same ID has already
     * been processed within the same candle interval.
     *
     * @param trade The trade to check for duplication
     * @return true if this trade is a duplicate, false if it's new
     */
    boolean isProcessed(Trade trade) {
        logger.atFine().log("Checking if trade is processed: ID=%s, timestamp=%d, pair=%s", 
            trade.getTradeId(), Timestamps.toString(trade.getTimestamp()), trade.getCurrencyPair());

        long intervalTimestamp = getMinuteTimestamp(Timestamps.toMillis(trade.getTimestamp()));
        logger.atFine().log("Calculated interval timestamp: %d", intervalTimestamp);

        // Create a unique key combining trade ID and its candle interval
        CandleKey key = CandleKey.create(trade.getTradeId(), intervalTimestamp);
        
        // Attempt to add to processed set - returns false if already present
        boolean isDuplicate = !processedTrades().add(key);
        
        if (isDuplicate) {
            logger.atInfo().log("Detected duplicate trade: ID=%s, timestamp=%s, pair=%s", 
                trade.getTradeId(), Timestamps.toString(trade.getTimestamp()), trade.getCurrencyPair());
        } else {
            logger.atFine().log("New trade detected: ID=%s, timestamp=%s, pair=%s", 
                trade.getTradeId(), Timestamps.toString(trade.getTimestamp()), trade.getCurrencyPair());
        }
        
        logger.atFine().log("Current processed trades count: %d", processedTrades().size());
        return isDuplicate;
    }

    /**
     * Calculates the start timestamp of the candle interval containing the given timestamp.
     *
     * @param timestamp A timestamp in milliseconds
     * @return The start timestamp of the containing candle interval
     */
    long getMinuteTimestamp(long timestamp) {
        long intervalTimestamp = (timestamp / candleIntervalMillis()) * candleIntervalMillis();
        logger.atFine().log("Converted timestamp %d to interval timestamp %d", 
            timestamp, intervalTimestamp);
        return intervalTimestamp;
    }

    /**
     * Immutable key combining a trade ID and candle interval timestamp for deduplication.
     */
    @AutoValue
    abstract static class CandleKey {
        private static CandleKey create(String tradeId, long minuteTimestamp) {
            logger.atFine().log("Creating new CandleKey: tradeId=%s, minuteTimestamp=%d", 
                tradeId, minuteTimestamp);
            return new AutoValue_TradeProcessor_CandleKey(tradeId, minuteTimestamp);
        }
    
        abstract String tradeId();
        abstract long minuteTimestamp();
    }
}
