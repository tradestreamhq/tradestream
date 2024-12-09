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
     * Checks if the given currency pair is supported by the exchange.
     * Default implementation always returns true until further implementation.
     *
     * @param currencyPair The currency pair to check (e.g., "BTC/USD").
     * @return true if the currency pair is supported, false otherwise.
     */
    default boolean isSupportedCurrencyPair(String currencyPair) {
        return true;
    }

    /**
     * Factory for creating exchange-specific streaming clients.
     */
    interface Factory {
        ExchangeStreamingClient create(String exchangeName);
    }
}
