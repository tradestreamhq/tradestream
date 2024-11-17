package com.verlumen.tradestream.ingestion;

import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import marketdata.Marketdata.Trade;
import marketdata.Marketdata.Candle;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

final class CandleManagerImpl implements CandleManager {
    private final Map<String, CandleBuilder> candleBuilders = new ConcurrentHashMap<>();
    private final PriceTracker priceTracker;
    private final long candleIntervalMillis;
    private final CandlePublisher candlePublisher;

    @Inject
    CandleManagerImpl(
        PriceTracker priceTracker,
        @Assisted long candleIntervalMillis,
        @Assisted CandlePublisher candlePublisher
    ) {
        this.priceTracker = priceTracker;
        this.candleIntervalMillis = candleIntervalMillis;
        this.candlePublisher = candlePublisher;
    }

    @Override
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

    @Override
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

    @Override
    public int getActiveBuilderCount() {
        return candleBuilders.size();
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
        candlePublisher.publishCandle(builder.build());
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
}
