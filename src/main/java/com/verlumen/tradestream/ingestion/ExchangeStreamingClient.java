package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Trade;

import java.util.function.Consumer; 

/**
 * Interface for exchange-specific streaming implementations.
 * This allows different exchanges to provide their own implementations
 * while maintaining a consistent interface for the data ingestion system.
 */
interface ExchangeStreamingClient {
    /**
     * Starts streaming market data for the given currency pairs.
     *
     * @param currencyPairs List of currency pairs to stream
     * @param tradeHandler Callback to handle incoming trades
     */
    void startStreaming(ImmutableList<String> currencyPairs, Consumer<Trade> tradeHandler);

    /**
     * Stops streaming and cleans up resources.
     */
    void stopStreaming();

    /**
     * Returns the name of the exchange (e.g., "coinbase", "binance").
     */
    String getExchangeName();

    /**
     * Factory for creating exchange-specific streaming clients.
     */
    interface Factory {       
        ExchangeStreamingClient getClient(String exchangeName);
    }
}
