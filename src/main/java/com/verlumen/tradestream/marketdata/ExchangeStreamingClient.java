package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;
import java.util.function.Consumer;

/**
 * Interface for exchange-specific streaming implementations.
 * This allows different exchanges to provide their own implementations
 * while maintaining a consistent interface for the data ingestion system.
 */
public interface ExchangeStreamingClient {
    /**
     * Starts streaming market data for the given currency pairs.
     *
     * @param currencyPairs List of currency pairs to stream
     * @param tradeHandler Callback to handle incoming trades
     */
    void startStreaming(ImmutableList<CurrencyPair> currencyPairs, Consumer<Trade> tradeHandler);

    /**
     * Stops streaming and cleans up resources.
     */
    void stopStreaming();

    /**
     * Returns the name of the exchange (e.g., "coinbase", "binance").
     */
    String getExchangeName();

    /**
     * Fetches the list of supported currency pairs from the Coinbase API.
     * 
     * @return an immutable list of supported CurrencyPairs.
     */
    ImmutableList<CurrencyPair> supportedCurrencyPairs();

    /**
     * Factory for creating exchange-specific streaming clients.
     */
    interface Factory {
        ExchangeStreamingClient create(String exchangeName);
    }
}
