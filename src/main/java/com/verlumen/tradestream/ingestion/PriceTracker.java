package com.verlumen.tradestream.ingestion;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

class PriceTracker {
    private final Map<String, Double> lastPrices = new ConcurrentHashMap<>();

    public void updateLastPrice(String currencyPair, double price) {
        lastPrices.put(currencyPair, price);
    }

    public double getLastPrice(String currencyPair) {
        return lastPrices.getOrDefault(currencyPair, Double.NaN);
    }

    public boolean hasPrice(String currencyPair) {
        return lastPrices.containsKey(currencyPair);
    }

    public void clear() {
        lastPrices.clear();
    }
}
