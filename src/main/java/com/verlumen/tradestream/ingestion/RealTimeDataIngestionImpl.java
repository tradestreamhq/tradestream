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
import com.verlumen.tradestream.marketdata.TradePublisher;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final Provider<CurrencyPairSupply> currencyPairSupply;
    private final ExchangeStreamingClient exchangeClient;
    private final TradePublisher tradePublisher;
    
    @Inject
    RealTimeDataIngestionImpl(
        Provider<CurrencyPairSupply> currencyPairSupply,
        ExchangeStreamingClient exchangeClient,
        TradePublisher tradePublisher
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupply = currencyPairSupply;
        this.exchangeClient = exchangeClient;
        this.tradePublisher = tradePublisher;
    }

    @Override
    public void start() {
        logger.atInfo().log("Starting real-time data ingestion for %s", 
            exchangeClient.getExchangeName());

        startMarketDataIngestion();

        logger.atInfo().log("Real-time data ingestion system fully initialized and running");
    }

    @Override
    public void shutdown() {
        logger.atInfo().log("Beginning shutdown sequence...");
        
        logger.atInfo().log("Stopping exchange streaming...");
        exchangeClient.stopStreaming();

        logger.atInfo().log("Closing trade publisher...");
        try {
            tradePublisher.close();
            logger.atInfo().log("Successfully closed trade publisher");
        } catch (Exception e) {
            logger.atWarning().withCause(e).log("Error closing trade publisher");
        }

        logger.atInfo().log("Shutdown sequence complete");
    }

    private void processTrade(Trade trade) {
        try {
            tradePublisher.publishTrade(trade);
        } catch (RuntimeException e) {
            logger.atSevere().withCause(e).log(
                "Error processing trade: %s", trade.getTradeId());
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
