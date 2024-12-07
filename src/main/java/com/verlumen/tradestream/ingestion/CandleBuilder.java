package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;

/**
 * Builds candle (OHLCV) data from a stream of trades for a specific currency pair and time interval.
 * This builder accumulates trade data and generates a candle representing price movements and volume
 * over the configured time period.
 *
 * <p>Thread-safety: This class is not thread-safe and should be accessed from a single thread,
 * or external synchronization should be used when accessed concurrently.
 *
 * <p>Usage example:
 * <pre>
 *   CandleBuilder builder = new CandleBuilder("BTC/USD", timestamp);
 *   builder.addTrade(trade1);
 *   builder.addTrade(trade2);
 *   Candle candle = builder.build();
 * </pre>
 */
final class CandleBuilder {
    // The currency pair this candle represents (e.g. "BTC/USD")
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final String currencyPair;
    
    // Unix timestamp in milliseconds marking the start of this candle's interval
    private final long timestamp;
    
    // Price tracking fields initialized to NaN to distinguish between no trades and zero prices
    private double open = Double.NaN;
    private double high = Double.NaN;
    private double low = Double.NaN;
    private double close = Double.NaN;
    
    // Accumulated volume for all trades in this candle's interval
    private double volume = 0.0;
    
    // Tracks whether any trades have been added to this builder
    private boolean hasTrades = false;

    /**
     * Creates a new CandleBuilder for the specified currency pair and timestamp.
     *
     * @param currencyPair The trading pair identifier (e.g. "BTC/USD")
     * @param timestamp The starting timestamp for this candle's interval in Unix milliseconds
     */
    CandleBuilder(String currencyPair, long timestamp) {
        logger.atInfo().log("Creating new CandleBuilder for %s at timestamp %d", currencyPair, timestamp);
        this.currencyPair = currencyPair;
        this.timestamp = timestamp;
    }

    /**
     * Adds a trade to this candle builder, updating OHLCV values appropriately.
     * The first trade added sets all price fields (O/H/L/C) to its price.
     * Subsequent trades update high/low water marks and the close price.
     *
     * @param trade The trade to process, must not be null
     */
    void addTrade(Trade trade) {
        logger.atInfo().log("Adding trade to candle for %s: price=%f, volume=%f", 
            currencyPair, trade.getPrice(), trade.getVolume());
        
        double price = trade.getPrice();
        double tradeVolume = trade.getVolume();

        // For first trade, initialize all price fields
        if (Double.isNaN(open)) {
            logger.atInfo().log("First trade for candle %s, initializing OHLC values to %f", 
                currencyPair, price);
            open = price;
            high = price;
            low = price;
        } else {
            // Update high/low water marks if applicable
            if (price > high) {
                logger.atInfo().log("New high price for %s: %f", currencyPair, price);
                high = price;
            }
            if (price < low) {
                logger.atInfo().log("New low price for %s: %f", currencyPair, price);
                low = price;
            }
        }

        // Most recent trade's price becomes the close
        close = price;
        logger.atFine().log("Updated close price for %s to %f", currencyPair, close);
        
        // Add this trade's volume to accumulated total
        volume += tradeVolume;
        logger.atFine().log("Updated accumulated volume for %s to %f", currencyPair, volume);
        
        hasTrades = true;
        logger.atFine().log("Candle state after trade: open=%f, high=%f, low=%f, close=%f, volume=%f",
            open, high, low, close, volume);
    }

    /**
     * Returns whether any trades have been added to this builder.
     *
     * @return true if at least one trade has been added, false otherwise
     */
    boolean hasTrades() {
        return hasTrades;
    }

    /**
     * Builds and returns a Candle representing all trades added to this builder.
     * Price fields will be NaN if no trades were added.
     *
     * @return A new immutable Candle instance
     */
    Candle build() {
        logger.atInfo().log("Building candle for %s: timestamp=%d, open=%f, high=%f, low=%f, close=%f, volume=%f",
            currencyPair, timestamp, open, high, low, close, volume);
        
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
