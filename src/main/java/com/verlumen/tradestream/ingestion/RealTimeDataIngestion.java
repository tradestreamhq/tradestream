package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final Provider<StreamingExchange> exchange;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        Provider<StreamingExchange> exchange,
        TradeProcessor tradeProcessor
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.exchange = exchange;
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
