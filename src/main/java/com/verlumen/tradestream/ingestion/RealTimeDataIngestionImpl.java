package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.collect.ImmutableSet.toImmutableSet;
import static com.google.common.collect.Sets.difference;
import static com.google.common.collect.Sets.intersection;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableSet;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Trade;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final String FORWARD_SLASH = "/";

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
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupply = currencyPairSupply;
        this.exchangeClient = exchangeClient;
        this.thinMarketTimer = thinMarketTimer;
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {
        logger.atInfo().log("Starting real-time data ingestion for %s", 
            exchangeClient.getExchangeName());

        startMarketDataIngestion();
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
        try {
            if (tradeProcessor.isProcessed(trade)) {
                logger.atInfo().log("Skipping duplicate trade for %s: ID=%s",
                    trade.getCurrencyPair(),
                    trade.getTradeId());
                return;
            }
            logger.atInfo().log("Processing new trade for %s: ID=%s, price=%f, volume=%f", 
                trade.getCurrencyPair(), 
                trade.getTradeId(),
                trade.getPrice(),
                trade.getVolume());
            candleManager.processTrade(trade);
        } catch (RuntimeException e) {
            logger.atSevere().withCause(e).log(
                "Error processing trade: %s", trade.getTradeId());
            // Don't rethrow - we want to continue processing other trades
        }
    }

    private void startMarketDataIngestion() {
        exchangeClient.startStreaming(supportedCurrencyPairs(), this::processTrade);
    }

    private ImmutableList<CurrencyPair> supportedCurrencyPairs() {
        ImmutableSet<CurrencyPair> supportedPairs = ImmutableSet.copyOf(
            exchangeClient.supportedCurrencyPairs());
        ImmutableSet<CurrencyPair> requestedPairs = ImmutableSet.copyOf(
            currencyPairSupply.get().currencyPairs());
        difference(requestedPairs, supportedPairs)
            .forEach(unsupportedPair -> logger.atInfo().log(
                "Pair with symbol %s is not supported.", unsupportedPair.symbol()));
        return intersection(requestedPairs, supportedPairs)
            .immutableCopy()
            .asList();
    }
}
