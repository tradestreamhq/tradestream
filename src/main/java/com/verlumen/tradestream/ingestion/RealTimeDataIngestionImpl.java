package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.marketdata.Trade;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final Provider<CurrencyPairSupply> currencyPairSupply;
    private final ExchangeStreamingClient exchangeClient;
    private final Provider<ThinMarketTimer> thinMarketTimer;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestionImpl(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        Provider<CurrencyPairSupply> currencyPairSupply,
        ExchangeStreamingClient exchangeClient,
        Provider<ThinMarketTimer> thinMarketTimer,
        TradeProcessor tradeProcessor
    ) {
        logger.atInfo().log("Initializing RealTimeDataIngestion implementation");
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupply = currencyPairSupply;
        this.exchangeClient = exchangeClient;
        this.thinMarketTimer = thinMarketTimer;
        this.tradeProcessor = tradeProcessor;
        logger.atInfo().log("RealTimeDataIngestion initialization complete");
    }

    @Override
    public void start() {
        logger.atInfo().log("Starting real-time data ingestion for %s", 
            exchangeClient.getExchangeName());
    
        exchangeClient.startStreaming(
            currencyPairSupply.get().symbols(),
            this::processTrade
        );
        
        logger.atInfo().log("Starting thin market timer...");
        thinMarketTimer.get().start();
        logger.atInfo().log("Real-time data ingestion system fully initialized and running");
    }

    @Override
    public void shutdown() {
        logger.atInfo().log("Beginning shutdown sequence...");
        
        logger.atInfo().log("Stopping exchange streaming...");
        exchangeClient.stopStreaming();

        logger.atInfo().log("Stopping thin market timer...");
        thinMarketTimer.get().stop();

        logger.atInfo().log("Closing candle publisher...");
        try {
            candlePublisher.close();
            logger.atInfo().log("Successfully closed candle publisher");
        } catch (Exception e) {
            logger.atWarning().withCause(e).log("Error closing candle publisher");
        }

        logger.atInfo().log("Shutdown sequence complete");
    }

    private void processTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            logger.atInfo().log("Processing new trade for %s: ID=%s, price=%f, volume=%f", 
                trade.getCurrencyPair(), 
                trade.getTradeId(),
                trade.getPrice(),
                trade.getVolume());
            candleManager.processTrade(trade);
        } else {
            logger.atInfo().log("Skipping duplicate trade for %s: ID=%s", 
                trade.getCurrencyPair(), 
                trade.getTradeId());
        }
    }
}
