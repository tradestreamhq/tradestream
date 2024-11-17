package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager.Factory candleManagerFactory;
    private final CandlePublisher.Factory candlePublisherFactory;
    private final Provider<StreamingExchange> exchange;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager.Factory candleManagerFactory,
        CandlePublisher.Factory candlePublisherFactory,
        Provider<StreamingExchange> exchange
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
