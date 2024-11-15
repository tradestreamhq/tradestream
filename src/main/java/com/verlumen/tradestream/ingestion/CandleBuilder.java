package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Candle;
import marketdata.Marketdata.Trade;

final class CandleBuilder {
    private final String currencyPair;
    private final long timestamp;
    private double open = Double.NaN;
    private double high = Double.NaN;
    private double low = Double.NaN;
    private double close = Double.NaN;
    private double volume = 0.0;
    private boolean hasTrades = false;

    CandleBuilder(String currencyPair, long timestamp) {
        this.currencyPair = currencyPair;
        this.timestamp = timestamp;
    }

    void addTrade(Trade trade) {
        double price = trade.getPrice();
        double tradeVolume = trade.getVolume();

        if (Double.isNaN(open)) {
            open = price;
            high = price;
            low = price;
        } else {
            high = Math.max(high, price);
            low = Math.min(low, price);
        }

        close = price;
        volume += tradeVolume;
        hasTrades = true;
    }

    boolean hasTrades() {
        return hasTrades;
    }

    Candle build() {
        return Candle.newBuilder()
                .setTimestamp(timestamp)
                .setCurrencyPair(currencyPair)
                .setOpen(open)
                .setHigh(high)
                .setLow(low)
                .setClose(close)
                .setVolume(volume)
                .build();
    }
}
