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
    private final CandlePublisher.Factory candlePublisherFactory;
    private final PriceTracker priceTracker;
    private final long candleIntervalMillis;
    private final String topic;

    @Inject
    CandleManagerImpl(
        CandlePublisher.Factory candlePublisherFactory,
        PriceTracker priceTracker,
        @Assisted long candleIntervalMillis,
        @Assisted String topic
    ) {
        this.candlePublisherFactory = candlePublisherFactory;
        this.priceTracker = priceTracker;
        this.candleIntervalMillis = candleIntervalMillis;
        this.topic = topic;
    }

    @Override
    public void processTrade(Trade trade) {
        long minuteTimestamp = getMinuteTimestamp(trade.getTimestamp());
        String key = getCandleKey(trade.getCurrencyPair(), minuteTimestamp);
        CandlePublisher publisher = createCandlePublisher();       
        CandleBuilder builder = candleBuilders.computeIfAbsent(
            key,
            k -> new CandleBuilder(trade.getCurrencyPair(), minuteTimestamp)
        );

        builder.addTrade(trade);
        priceTracker.updateLastPrice(trade.getCurrencyPair(), trade.getPrice());

        if (isIntervalComplete(minuteTimestamp)) {
            publishAndRemoveCandle(publisher, key, builder);
        }
    }

    @Override
    public void handleThinlyTradedMarkets(List<String> currencyPairs) {
        long currentMinute = getMinuteTimestamp(System.currentTimeMillis());
        CandlePublisher publisher = createCandlePublisher();
        for (String pair : currencyPairs) {
            String key = getCandleKey(pair, currentMinute);
            CandleBuilder builder = candleBuilders.get(key);
            
            if (builder == null || !builder.hasTrades()) {
                generateEmptyCandle(publisher, pair, currentMinute);
            }
        }
    }

    private CandlePublisher createCandlePublisher() {
        return candlePublisherFactory.create(topic);
    }

    private void generateEmptyCandle(CandlePublisher publisher, String currencyPair, long timestamp) {
        double lastPrice = priceTracker.getLastPrice(currencyPair);
        if (!Double.isNaN(lastPrice)) {
            CandleBuilder builder = new CandleBuilder(currencyPair, timestamp);
            builder.addTrade(Trade.newBuilder()
                .setPrice(lastPrice)
                .setVolume(0)
                .setCurrencyPair(currencyPair)
                .setTimestamp(timestamp)
                .build());
            publishAndRemoveCandle(publisher, getCandleKey(currencyPair, timestamp), builder);
        }
    }

    private void publishAndRemoveCandle(CandlePublisher publisher, String key, CandleBuilder builder) {
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
