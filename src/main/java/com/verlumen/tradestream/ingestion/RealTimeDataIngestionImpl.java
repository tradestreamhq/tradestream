package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.marketdata.Trade;
import info.bitrich.xchangestream.core.ProductSubscription;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.disposables.Disposable;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final Provider<CurrencyPairSupply> currencyPairSupply;
    private final Provider<StreamingExchange> exchange;
    private final List<Disposable> subscriptions;
    private final Provider<ThinMarketTimer> thinMarketTimer;
    private final TradeProcessor tradeProcessor;
    
    // Add counters for monitoring
    private final AtomicInteger totalTradesReceived = new AtomicInteger(0);
    private final AtomicInteger totalTradesProcessed = new AtomicInteger(0);
    private final AtomicInteger duplicateTradesDetected = new AtomicInteger(0);
    private final AtomicInteger errorCount = new AtomicInteger(0);
    
    @Inject
    RealTimeDataIngestionImpl(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        Provider<CurrencyPairSupply> currencyPairSupply,
        Provider<StreamingExchange> exchange,
        Provider<ThinMarketTimer> thinMarketTimer,
        TradeProcessor tradeProcessor
    ) {
        logger.atInfo().log("Initializing RealTimeDataIngestion implementation");
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupply = currencyPairSupply;
        this.exchange = exchange;
        this.subscriptions = new ArrayList<>();
        this.thinMarketTimer = thinMarketTimer;
        this.tradeProcessor = tradeProcessor;
        logger.atInfo().log("RealTimeDataIngestion initialization complete");
    }

    @Override
    public void start() {
        ImmutableList<CurrencyPair> currencyPairs = currencyPairSupply.get().currencyPairs();

        logger.atInfo().log("Starting real-time data ingestion with %d currency pairs: %s", 
            currencyPairs.size(), currencyPairs);
    
        try {
            connectToExchange(currencyPairs);
            logger.atInfo().log("Exchange connected successfully! Exchange status: alive=%b, subscription count=%d", 
                exchange.get().isAlive(), currencyPairs.size());
            
            logger.atInfo().log("Starting trade stream subscriptions...");
            subscribeToTradeStreams();
            
            logger.atInfo().log("Starting thin market timer...");
            thinMarketTimer.get().start();
            
            logger.atInfo().log("Real-time data ingestion system fully initialized and running");
            
            // Log initial system state
            logSystemState();
        } catch (Exception e) {
            errorCount.incrementAndGet();
            logger.atSevere().withCause(e).log("Critical error during system startup");
            throw e;
        }
    }

    @Override
    public void shutdown() {
        logger.atInfo().log("Beginning shutdown sequence... Final system state:");
        logSystemState();
        
        logger.atInfo().log("Disposing of %d subscriptions", subscriptions.size());
        subscriptions.forEach(disposable -> {
            try {
                disposable.dispose();
                logger.atFine().log("Successfully disposed of subscription");
            } catch (Exception e) {
                errorCount.incrementAndGet();
                logger.atWarning().withCause(e).log("Error disposing subscription");
            }
        });

        logger.atInfo().log("Stopping thin market timer...");
        thinMarketTimer.get().stop();

        logger.atInfo().log("Disconnecting from exchange...");
        try {
            exchange.get().disconnect().blockingAwait();
            logger.atInfo().log("Successfully disconnected from exchange");
        } catch (Exception e) {
            errorCount.incrementAndGet();
            logger.atWarning().withCause(e).log("Error disconnecting from exchange");
        }

        logger.atInfo().log("Closing candle publisher...");
        try {
            candlePublisher.close();
            logger.atInfo().log("Successfully closed candle publisher");
        } catch (Exception e) {
            errorCount.incrementAndGet();
            logger.atWarning().withCause(e).log("Error closing candle publisher");
        }

        logger.atInfo().log("Shutdown sequence complete. Final error count: %d", errorCount.get());
    }

    private void connectToExchange(ImmutableList<CurrencyPair> currencyPairs) {
        logger.atInfo().log("Connecting to exchange...");
        ProductSubscription productSubscription = createProductSubscription(currencyPairs);
        try {
            exchange.get().connect(productSubscription).blockingAwait();
            logger.atInfo().log("Successfully connected to exchange and subscribed to %d currency pairs", 
                currencyPairs.size());
        } catch (Exception e) {
            errorCount.incrementAndGet();
            logger.atSevere().withCause(e)
                .log("Failed to connect to exchange or subscribe to currency pairs");
            throw e;
        }
    }

    private Trade convertTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String pair) {
        logger.atFine().log("Converting trade for pair %s: price=%f, volume=%f, id=%s", 
            pair, 
            xchangeTrade.getPrice().doubleValue(), 
            xchangeTrade.getOriginalAmount().doubleValue(),
            xchangeTrade.getId());

        String tradeId = xchangeTrade.getId() != null ? 
            xchangeTrade.getId() : 
            UUID.randomUUID().toString();

        if (xchangeTrade.getId() == null) {
            logger.atWarning().log("Trade ID was null for %s trade, generated UUID: %s", pair, tradeId);
        }

        Trade trade = Trade.newBuilder()
            .setTimestamp(xchangeTrade.getTimestamp().getTime())
            .setExchange(exchange.get().getExchangeSpecification().getExchangeName())
            .setCurrencyPair(pair)
            .setPrice(xchangeTrade.getPrice().doubleValue())
            .setVolume(xchangeTrade.getOriginalAmount().doubleValue())
            .setTradeId(tradeId)
            .build();

        logger.atFine().log("Successfully converted trade: %s", trade);
        return trade;
    }

    private ProductSubscription createProductSubscription(ImmutableList<CurrencyPair> currencyPairs) {
        ProductSubscription.ProductSubscriptionBuilder builder = ProductSubscription.create();
        currencyPairs.forEach(builder::addTrades);
        return builder.build();
    }

    private void handleTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String currencyPair) {
        totalTradesReceived.incrementAndGet();
        logger.atFine().log("Processing incoming trade for %s", currencyPair);
        
        try {
            Trade trade = convertTrade(xchangeTrade, currencyPair);
            onTrade(trade);
        } catch (Exception e) {
            errorCount.incrementAndGet();
            logger.atSevere().withCause(e)
                .log("Error processing trade for %s: price=%f, volume=%f", 
                    currencyPair,
                    xchangeTrade.getPrice().doubleValue(),
                    xchangeTrade.getOriginalAmount().doubleValue());
        }
    }

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            logger.atInfo().log("Processing new trade for %s: ID=%s, price=%f, volume=%f", 
                trade.getCurrencyPair(), 
                trade.getTradeId(),
                trade.getPrice(),
                trade.getVolume());
            try {
                candleManager.processTrade(trade);
                totalTradesProcessed.incrementAndGet();
            } catch (Exception e) {
                errorCount.incrementAndGet();
                logger.atSevere().withCause(e)
                    .log("Failed to process trade: %s", trade);
            }
        } else {
            duplicateTradesDetected.incrementAndGet();
            logger.atInfo().log("Skipping duplicate trade for %s: ID=%s", 
                trade.getCurrencyPair(), 
                trade.getTradeId());
        }
    }

    private void subscribeToTradeStreams() {
        logger.atInfo().log("Setting up trade stream subscriptions for %d currency pairs", 
            currencyPairSupply.get().currencyPairs().size());

        currencyPairSupply.get().currencyPairs().stream()
            .map(pair -> {
                logger.atFine().log("Creating subscription for %s", pair);
                return subscribeToTradeStream(pair);
            })
            .forEach(subscription -> {
                subscriptions.add(subscription);
                logger.atFine().log("Added subscription, total count: %d", subscriptions.size());
            });

        logger.atInfo().log("Successfully created %d trade stream subscriptions", 
            subscriptions.size());
    }

    private Disposable subscribeToTradeStream(CurrencyPair currencyPair) {
        logger.atInfo().log("Creating trade stream subscription for currency pair: %s", currencyPair);
        
        return exchange.get()
            .getStreamingMarketDataService()
            .getTrades(currencyPair)
            .doOnSubscribe(d -> logger.atInfo().log("Successfully subscribed to %s trade stream", currencyPair))
            .doOnError(e -> {
                errorCount.incrementAndGet();
                logger.atSevere().withCause(e)
                    .log("Error in trade stream for %s", currencyPair);
            })
            .doOnComplete(() -> logger.atInfo().log("Trade stream completed for %s", currencyPair))
            .subscribe(
                trade -> {
                    logger.atInfo().log("Received trade for %s: price=%f, amount=%f, id=%s", 
                        currencyPair, 
                        trade.getPrice().doubleValue(), 
                        trade.getOriginalAmount().doubleValue(),
                        trade.getId());
                    handleTrade(trade, currencyPair.toString());
                },
                throwable -> {
                    errorCount.incrementAndGet();
                    logger.atSevere().withCause(throwable)
                        .log("Fatal error in trade stream for %s", currencyPair);
                });
    }

    private void logSystemState() {
        logger.atInfo().log(
            "System State - Total Trades: received=%d, processed=%d, duplicates=%d, errors=%d, " +
            "active subscriptions=%d, active builders=%d",
            totalTradesReceived.get(),
            totalTradesProcessed.get(),
            duplicateTradesDetected.get(),
            errorCount.get(),
            subscriptions.size(),
            candleManager.getActiveBuilderCount()
        );
    }
}

    private void logSystemState() {
        logger.atInfo().log(
            "System State - Total Trades: received=%d, processed=%d, duplicates=%d, errors=%d, " +
            "active subscriptions=%d, active builders=%d",
            totalTradesReceived.get(),
            totalTradesProcessed.get(),
            duplicateTradesDetected.get(),
            errorCount.get(),
            subscriptions.size(),
            candleManager.getActiveBuilderCount()
        );
    }

    private void subscribeToTradeStreams() {
        logger.atInfo().log("Setting up trade stream subscriptions for %d currency pairs", 
            currencyPairSupply.get().currencyPairs().size());

        currencyPairSupply.get().currencyPairs().stream()
            .map(pair -> {
                logger.atFine().log("Creating subscription for %s", pair);
                return subscribeToTradeStream(pair);
            })
            .forEach(subscription -> {
                subscriptions.add(subscription);
                logger.atFine().log("Added subscription, total count: %d", subscriptions.size());
            });

        logger.atInfo().log("Successfully created %d trade stream subscriptions", 
            subscriptions.size());
    }
}
