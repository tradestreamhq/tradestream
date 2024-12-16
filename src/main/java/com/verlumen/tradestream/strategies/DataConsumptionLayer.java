package com.verlumen.tradestream.strategies.dataconsumption;

import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.util.List;

/**
 * Handles the consumption and organization of candle data from the ingestion module.
 * Provides access to candle data across multiple timeframes through a sliding window.
 */
public interface DataConsumptionLayer {
    /**
     * Consumes a new candle, updating all relevant timeframe windows.
     * 
     * @param candle The new candle to process
     */
    void consumeCandle(Candle candle);

    /**
     * Retrieves candles for a specific timeframe within a sliding window.
     *
     * @param timeframe The duration of each candle
     * @param windowSize The number of candles to include in the window
     * @param currencyPair The currency pair to retrieve data for
     * @return List of candles in chronological order
     */
    List<Candle> getCandlesForTimeframe(Duration timeframe, int windowSize, String currencyPair);

    /**
     * Returns the list of supported timeframes.
     */
    List<Duration> getSupportedTimeframes();

    /**
     * Interface for providing configuration to the DataConsumptionLayer.
     */
    interface Config {
        String getKafkaTopic();
        String getKafkaBootstrapServers();
        List<Duration> getSupportedTimeframes();
        Duration getBaseCandleTimeframe();
    }

    /**
     * Factory for creating DataConsumptionLayer instances.
     */
    interface Factory {
        DataConsumptionLayer create(Config config);
    }
}
