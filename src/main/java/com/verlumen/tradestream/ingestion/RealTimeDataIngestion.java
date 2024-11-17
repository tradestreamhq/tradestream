package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager.Factory candleManagerFactory;
    private final CandlePublisher.Factory candlePublisherFactory;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager.Factory candleManagerFactory,
        CandlePublisher.Factory candlePublisherFactory,
        TradeProcessor tradeProcessor,
    ) {
        this.candleManagerFactory = candleManagerFactory;
        this.candlePublisherFactory = candlePublisherFactory;
        this.tradeProcessor = tradeProcessor; 
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
