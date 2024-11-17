package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager.Factory candleManagerFactory;
    private final CandlePublisher.Factory candlePublisherFactory;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager.Factory candleManagerFactory,
        CandlePublisher.Factory candlePublisherFactory,
    ) {
        this.candleManagerFactory = candleManagerFactory;
        this.candlePublisherFactory = candlePublisherFactory;
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
