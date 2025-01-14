package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Tracks the latest price for each currency pair to support generation of empty candles
 * during periods of low trading activity. This allows the system to maintain price continuity
 * even when no trades occur during a candle interval.
 *
 * <p>Thread-safety: This class is thread-safe through use of ConcurrentHashMap for internal
 * state management.
 */
class PriceTracker {
    // Thread-safe map storing the most recent price for each currency pair
    private final Map<String, Double> lastPrices = new ConcurrentHashMap<>();

    @Inject
    PriceTracker() {}

    /**
     * Updates the last known price for a currency pair.
     *
     * @param currencyPair The currency pair identifier (e.g. "BTC/USD")
     * @param price The new price to record
     */
    void updateLastPrice(String currencyPair, double price) {
        lastPrices.put(currencyPair, price);
    }

    /**
     * Retrieves the last known price for a currency pair.
     *
     * @param currencyPair The currency pair to look up
     * @return The last known price, or Double.NaN if no price is available
     */
    double getLastPrice(String currencyPair) {
        return lastPrices.getOrDefault(currencyPair, Double.NaN);
    }

    /**
     * Checks if a price exists for the given currency pair.
     *
     * @param currencyPair The currency pair to check
     * @return true if a price exists, false otherwise
     */
    boolean hasPrice(String currencyPair) {
        return lastPrices.containsKey(currencyPair);
    }

    /**
     * Clears all stored prices. Useful for testing or resetting state.
     */
    void clear() {
        lastPrices.clear();
    }
}
