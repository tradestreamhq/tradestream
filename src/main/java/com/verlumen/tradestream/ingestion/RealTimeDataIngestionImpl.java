package com.verlumen.tradestream.ingestion;

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
import java.util.concurrent.TimeUnit;

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final int RESUBSCRIBE_DELAY_SECONDS = 5;
    private static final int MAX_RESUBSCRIBE_ATTEMPTS = 3;

    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final Provider<CurrencyPairSupply> currencyPairSupply;
    private final Provider<StreamingExchange> exchange;
    private final Provider<ProductSubscription> productSubscription;
    private final List<Disposable> subscriptions;
    private final Provider<ThinMarketTimer> thinMarketTimer;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestionImpl(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        Provider<CurrencyPairSupply> currencyPairSupply,
        Provider<StreamingExchange> exchange,
        Provider<ProductSubscription> productSubscription,
        Provider<ThinMarketTimer> thinMarketTimer,
        TradeProcessor tradeProcessor
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupply = currencyPairSupply;
        this.exchange = exchange;
        this.productSubscription = productSubscription;
        this.subscriptions = new ArrayList<>();
        this.thinMarketTimer = thinMarketTimer;
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {
        StreamingExchange streamingExchange = exchange.get();
        logger.atInfo().log("Starting real-time data ingestion with %d currency pairs from %s", 
            currencyPairSupply.get().currencyPairs().size(),
            streamingExchange.getExchangeSpecification().getExchangeName());
        
        streamingExchange.connect(productSubscription.get())
            .doOnComplete(() -> {
                logger.atInfo().log("Exchange connected successfully! API URL: %s", 
                    streamingExchange.getExchangeSpecification().getSslUri());
                subscribeToTradeStreams();
                thinMarketTimer.get().start();
                logger.atInfo().log("Real-time data ingestion started successfully");
            })
            .doOnError(throwable -> {
                logger.atSevere().withCause(throwable).log(
                    "Failed to connect to exchange. Active subscriptions: %d",
                    subscriptions.size());
            })
            .subscribe();
    }

    @Override
    public void shutdown() {
        logger.atInfo().log("Initiating shutdown sequence");
        subscriptions.forEach(Disposable::dispose);
        thinMarketTimer.get().stop();
        exchange.get().disconnect().blockingAwait();
        logger.atInfo().log("Disposed %d subscriptions", subscriptions.size());
        candlePublisher.close();
        logger.atInfo().log("Real-time data ingestion shutdown complete");
    }

    private Disposable subscribeToTradeStream(CurrencyPair currencyPair) {
        logger.atInfo().log("Subscribing to trade stream for currency pair: %s", currencyPair);
        
        return exchange.get()
            .getStreamingMarketDataService()
            .getTrades(currencyPair)
            .doOnSubscribe(disposable -> 
                logger.atInfo().log("Successfully subscribed to %s trade stream", currencyPair))
            .doOnNext(trade -> 
                logger.atInfo().log("Received trade for %s: price=%f, amount=%f, id=%s", 
                    currencyPair, 
                    trade.getPrice().doubleValue(),
                    trade.getOriginalAmount().doubleValue(),
                    trade.getId()))
            .doOnError(throwable -> 
                logger.atSevere().withCause(throwable)
                    .log("Error in trade stream for %s", currencyPair))
            .subscribe(
                trade -> handleTrade(trade, currencyPair.toString()),
                throwable -> {
                    logger.atSevere().withCause(throwable)
                        .log("Error subscribing to %s", currencyPair);
                    resubscribeWithDelay(currencyPair, 1);
                });
    }

    private void resubscribeWithDelay(CurrencyPair currencyPair, int attemptCount) {
        if (attemptCount > MAX_RESUBSCRIBE_ATTEMPTS) {
            logger.atSevere().log("Maximum resubscribe attempts (%d) reached for %s", 
                MAX_RESUBSCRIBE_ATTEMPTS, currencyPair);
            return;
        }

        logger.atInfo().log("Scheduling resubscription attempt %d for %s in %d seconds", 
            attemptCount, currencyPair, RESUBSCRIBE_DELAY_SECONDS);

        Observable.timer(RESUBSCRIBE_DELAY_SECONDS, TimeUnit.SECONDS)
            .subscribe(ignored -> {
                logger.atInfo().log("Attempting resubscription for %s (attempt %d)", 
                    currencyPair, attemptCount);
                Disposable newSubscription = subscribeToTradeStream(currencyPair)
                    .doOnError(throwable -> resubscribeWithDelay(currencyPair, attemptCount + 1));
                subscriptions.add(newSubscription);
            });
    }

    private void subscribeToTradeStreams() {
        currencyPairSupply.get().currencyPairs().stream()
            .map(this::subscribeToTradeStream)
            .forEach(subscriptions::add);
        logger.atInfo().log("Subscribed to %d trade streams", subscriptions.size());
    }

    private void handleTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, 
        String currencyPair) {
        Trade trade = convertTrade(xchangeTrade, currencyPair);
        if (!tradeProcessor.isProcessed(trade)) {
            logger.atInfo().log("Processing new trade for %s: ID=%s, Price=%f, Volume=%f", 
                trade.getCurrencyPair(), trade.getTradeId(), 
                trade.getPrice(), trade.getVolume());
            candleManager.processTrade(trade);
        } else {
            logger.atFine().log("Skipping duplicate trade for %s: ID=%s",
                trade.getCurrencyPair(), trade.getTradeId());
        }
    }

    private Trade convertTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String pair) {
        return Trade.newBuilder()
            .setTimestamp(xchangeTrade.getTimestamp().getTime())
            .setExchange(exchange.get().getExchangeSpecification().getExchangeName())
            .setCurrencyPair(pair)
            .setPrice(xchangeTrade.getPrice().doubleValue())
            .setVolume(xchangeTrade.getOriginalAmount().doubleValue())
            .setTradeId(xchangeTrade.getId() != null ? xchangeTrade.getId() : 
                UUID.randomUUID().toString())
            .build();
    }
}
