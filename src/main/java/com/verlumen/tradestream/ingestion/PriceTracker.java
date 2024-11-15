package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

class PriceTracker {
    private final Map<String, Double> lastPrices = new ConcurrentHashMap<>();

    @Inject
    PriceTracker() {}

    void updateLastPrice(String currencyPair, double price) {
        lastPrices.put(currencyPair, price);
    }

    double getLastPrice(String currencyPair) {
        return lastPrices.getOrDefault(currencyPair, Double.NaN);
    }

    boolean hasPrice(String currencyPair) {
        return lastPrices.containsKey(currencyPair);
    }

    void clear() {
        lastPrices.clear();
    }
}
