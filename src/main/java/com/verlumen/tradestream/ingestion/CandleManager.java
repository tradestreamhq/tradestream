package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Trade;
import marketdata.Marketdata.Candle;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

class CandleManager {
    private final Map<String, CandleBuilder> candleBuilders = new ConcurrentHashMap<>();
    private final long candleIntervalMillis;
    private final CandlePublisher publisher;
    private final PriceTracker priceTracker;

    CandleManager(long candleIntervalMillis, CandlePublisher publisher, PriceTracker priceTracker) {
        this.candleIntervalMillis = candleIntervalMillis;
        this.publisher = publisher;
        this.priceTracker = priceTracker;
    }

    public void processTrade(Trade trade) {
        long minuteTimestamp = getMinuteTimestamp(trade.getTimestamp());
        String key = getCandleKey(trade.getCurrencyPair(), minuteTimestamp);
        
        CandleBuilder builder = candleBuilders.computeIfAbsent(
            key,
            k -> new CandleBuilder(trade.getCurrencyPair(), minuteTimestamp)
        );

        builder.addTrade(trade);
        priceTracker.updateLastPrice(trade.getCurrencyPair(), trade.getPrice());

        if (isIntervalComplete(minuteTimestamp)) {
            publishAndRemoveCandle(key, builder);
        }
    }

    public void handleThinlyTradedMarkets(List<String> currencyPairs) {
        long currentMinute = getMinuteTimestamp(System.currentTimeMillis());
        for (String pair : currencyPairs) {
            String key = getCandleKey(pair, currentMinute);
            CandleBuilder builder = candleBuilders.get(key);
            
            if (builder == null || !builder.hasTrades()) {
                generateEmptyCandle(pair, currentMinute);
            }
        }
    }

    private void generateEmptyCandle(String currencyPair, long timestamp) {
        double lastPrice = priceTracker.getLastPrice(currencyPair);
        if (!Double.isNaN(lastPrice)) {
            CandleBuilder builder = new CandleBuilder(currencyPair, timestamp);
            builder.addTrade(Trade.newBuilder()
                .setPrice(lastPrice)
                .setVolume(0)
                .setCurrencyPair(currencyPair)
                .setTimestamp(timestamp)
                .build());
            publishAndRemoveCandle(getCandleKey(currencyPair, timestamp), builder);
        }
    }

    private void publishAndRemoveCandle(String key, CandleBuilder builder) {
        publisher.publishCandle(builder.build());
        candleBuilders.remove(key);
    }

    private String getCandleKey(String currencyPair, long minuteTimestamp) {
        return currencyPair + ":" + minuteTimestamp;
    }

    private long getMinuteTimestamp(long timestamp) {
        return (timestamp / candleIntervalMillis) * candleIntervalMillis;
    }

    private boolean isIntervalComplete(long timestamp) {
        return System.currentTimeMillis() >= timestamp + candleIntervalMillis;
    }

    // Visible for testing
    int getActiveBuilderCount() {
        return candleBuilders.size();
    }
}
