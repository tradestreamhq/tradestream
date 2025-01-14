package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.flogger.FluentLogger;
import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

final class CandleManagerImpl implements CandleManager {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
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
        logger.atInfo().log("Initializing CandleManager with interval: %d ms", candleIntervalMillis);
        this.priceTracker = priceTracker;
        this.candleIntervalMillis = candleIntervalMillis;
        this.candlePublisher = candlePublisher;
        logger.atInfo().log("CandleManager initialization complete");
    }

    @Override
    public void processTrade(Trade trade) {
        long minuteTimestamp = getMinuteTimestamp(Timestamps.toMillis(trade.getTimestamp()));
        String key = getCandleKey(trade.getCurrencyPair(), minuteTimestamp);
        logger.atFine().log("Processing trade for candle key: %s, trade ID: %s, price: %f", 
            key, trade.getTradeId(), trade.getPrice());

        CandleBuilder builder = candleBuilders.computeIfAbsent(
            key,
            k -> {
                logger.atInfo().log("Creating new candle builder for %s at timestamp %d",
                    trade.getCurrencyPair(), minuteTimestamp);
                return CandleBuilder.create(trade.getCurrencyPair(), minuteTimestamp);
            }
        );

        builder.addTrade(trade);
        logger.atFine().log("Updated candle builder for %s with trade: price=%f, volume=%f",
            key, trade.getPrice(), trade.getVolume());

        priceTracker.updateLastPrice(trade.getCurrencyPair(), trade.getPrice());
        logger.atFine().log("Updated last price for %s to %f", 
            trade.getCurrencyPair(), trade.getPrice());

        if (isIntervalComplete(minuteTimestamp)) {
            logger.atInfo().log("Interval complete for %s, publishing candle", key);
            publishAndRemoveCandle(key, builder);
        }
    }

    @Override
    public void handleThinlyTradedMarkets(List<CurrencyPair> currencyPairs) {
        logger.atInfo().log("Handling thin market update for %d currency pairs", currencyPairs.size());
        long currentMinute = getMinuteTimestamp(System.currentTimeMillis());
        
        for (CurrencyPair pair : currencyPairs) {
            String key = getCandleKey(pair.symbol(), currentMinute);
            CandleBuilder builder = candleBuilders.get(key);
            
            if (builder == null || !builder.hasTrades()) {
                logger.atInfo().log("No trades found for %s in current interval, generating empty candle", pair.symbol());
                generateEmptyCandle(pair.symbol(), currentMinute);
            } else {
                logger.atFine().log("Skipping thin market handling for %s - active trades exist", pair.symbol());
            }
        }
        logger.atInfo().log("Completed thin market handling for %d pairs", currencyPairs.size());
    }

    @Override
    public int getActiveBuilderCount() {
        int count = candleBuilders.size();
        logger.atFine().log("Current active builder count: %d", count);
        return count;
    }

    private void generateEmptyCandle(String symbol, long timestamp) {
        double lastPrice = priceTracker.getLastPrice(symbol);
        logger.atInfo().log("Generating empty candle for %s at timestamp %d with last price %f",
            symbol, timestamp, lastPrice);

        if (Double.isNaN(lastPrice)) {
            logger.atWarning().log("No last price available for %s, unable to generate empty candle", 
                symbol);
            return;
        }
            
        logger.atInfo().log("Creating empty candle with last known price %f for %s", 
            lastPrice, symbol);
        CandleBuilder builder = CandleBuilder.create(symbol, timestamp);
        builder.addTrade(Trade.newBuilder()
            .setPrice(lastPrice)
            .setVolume(0)
            .setCurrencyPair(symbol)
            .setTimestamp(Timestamps.fromMillis(timestamp))
            .build());
        publishAndRemoveCandle(getCandleKey(symbol, timestamp), builder);
    }

    private void publishAndRemoveCandle(String key, CandleBuilder builder) {
        Candle candle = builder.build();
        logger.atInfo().log("Publishing candle for %s: timestamp=%s, open=%f, high=%f, low=%f, close=%f, volume=%f",
            candle.getCurrencyPair(), 
            Timestamps.toString(candle.getTimestamp()),
            candle.getOpen(),
            candle.getHigh(),
            candle.getLow(),
            candle.getClose(),
            candle.getVolume());
                
        candlePublisher.publishCandle(candle);
        candleBuilders.remove(key);
        logger.atInfo().log("Removed builder for key %s, active builders remaining: %d", 
            key, candleBuilders.size());
    }

    private String getCandleKey(String symbol, long minuteTimestamp) {
        return symbol + ":" + minuteTimestamp;
    }

    private long getMinuteTimestamp(long timestamp) {
        return (timestamp / candleIntervalMillis) * candleIntervalMillis;
    }

    private boolean isIntervalComplete(long timestamp) {
        boolean isComplete = System.currentTimeMillis() >= timestamp + candleIntervalMillis;
        if (isComplete) {
            logger.atFine().log("Interval complete for timestamp %d", timestamp);
        }
        return isComplete;
    }
}
