package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandlePublisher.Factory candlePublisherFactory;
    
    @Inject
    RealTimeDataIngestion(CandlePublisher.Factory candlePublisherFactory) {
        this.candlePublisherFactory = candlePublisherFactory;
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
