package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandlePublisher candlePublisher;
    
    @Inject
    RealTimeDataIngestion(CandlePublisher candlePublisher) {
        this.candlePublisher = candlePublisher;
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
