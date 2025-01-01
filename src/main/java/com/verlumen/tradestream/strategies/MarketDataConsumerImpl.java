package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import java.util.function.Consumer;

/**
 * Consumes candle data from a Kafka topic using the Kafka Consumer API.
 * Supports graceful shutdown and error handling.
 */
final class MarketDataConsumerImpl implements MarketDataConsumer {
    @Inject
    MarketDataConsumerImpl() {}

    @Override
    public synchronized void startConsuming(Consumer<Candle> handler) {
      throw new UnsupportedOperationException();
    }

    @Override
    public synchronized void stopConsuming() {
      throw new UnsupportedOperationException();
    }
}
