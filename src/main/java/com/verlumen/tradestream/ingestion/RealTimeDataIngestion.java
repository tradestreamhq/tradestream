package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager.Factory candleManagerFactory;
    private final CandlePublisher.Factory candlePublisherFactory;
    private final StreamingExchange exchange;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager.Factory candleManagerFactory,
        CandlePublisher.Factory candlePublisherFactory,
        StreamingExchange exchange
    ) {
        this.candleManagerFactory = candleManagerFactory;
        this.candlePublisherFactory = candlePublisherFactory;
        this.exchange = exchange;
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
