package com.verlumen.tradestream.strategies;

import com.verlumen.tradestream.marketdata.Candle;
import java.util.function.Consumer;

/**
 * Interface for consuming market data from Kafka and forwarding it to
 * registered handlers.
 */
public interface MarketDataConsumer {
    /**
     * Starts consuming market data and forwards it to the provided handler.
     *
     * @param handler Consumer that will process each candle
     */
    void startConsuming(Consumer<Candle> handler);

    /**
     * Stops consuming market data and performs cleanup.
     */
    void stopConsuming();

    interface Factory {
        MarketDataConsumer create(String candleTopic);
    }
}
