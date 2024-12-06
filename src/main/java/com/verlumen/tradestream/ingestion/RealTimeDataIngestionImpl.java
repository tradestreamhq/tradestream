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

final class RealTimeDataIngestionImpl implements RealTimeDataIngestion {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

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
      logger.atInfo().log("Starting real-time data ingestion with %d currency pairs", 
          currencyPairSupply.get().currencyPairs().size());
      exchange.get().connect(productSubscription.get())
          .subscribe(() -> {
              logger.atInfo().log("Exchange connected successfully!");
              subscribeToTradeStreams();
              thinMarketTimer.get().start();
              logger.atInfo().log("Real-time data ingestion started successfully");
          }, throwable -> {
              logger.atSevere().withCause(throwable).log("Error connecting to exchange");
              logger.atInfo().log("Active subscriptions: %d", subscriptions.size());
              logger.atSevere().log("Connection error details: %s", throwable.getMessage());
          });
    }

    @Override
    public void shutdown() {
        subscriptions.forEach(Disposable::dispose);
        thinMarketTimer.get().stop();
        exchange.get().disconnect().blockingAwait();
        logger.atInfo().log("Disposed %d subscriptions", subscriptions.size());
        candlePublisher.close();
        logger.atInfo().log("Real-time data ingestion shutdown complete");
    }

    private Trade convertTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String pair) {
        logger.atFine().log("Converting trade for pair %s: price=%f, volume=%f", 
            pair, xchangeTrade.getPrice().doubleValue(), xchangeTrade.getOriginalAmount().doubleValue());
        return Trade.newBuilder()
            .setTimestamp(xchangeTrade.getTimestamp().getTime())
            .setExchange(exchange.get().getExchangeSpecification().getExchangeName())
            .setCurrencyPair(pair)
            .setPrice(xchangeTrade.getPrice().doubleValue())
            .setVolume(xchangeTrade.getOriginalAmount().doubleValue())
            .setTradeId(xchangeTrade.getId() != null ? xchangeTrade.getId() : UUID.randomUUID().toString())
            .build();
    }

    private void handleTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String currencyPair) {
        String symbol = currencyPair.toString();
        Trade trade = convertTrade(xchangeTrade, symbol);
        onTrade(trade);
    }

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            logger.atFine().log("Processing new trade for %s: ID=%s", 
                trade.getCurrencyPair(), trade.getTradeId());
            candleManager.processTrade(trade);
        } else {
            logger.atFine().log("Skipping duplicate trade for %s: ID=%s",
                trade.getCurrencyPair(), trade.getTradeId());
        }
    }

    private Disposable subscribeToTradeStream(CurrencyPair currencyPair) {
        logger.atInfo().log("Subscribing to trade stream for currency pair: %s", currencyPair);
        return exchange.get()
            .getStreamingMarketDataService()
            .getTrades(currencyPair)
            .subscribe(
                trade -> handleTrade(trade, currencyPair.toString()),
                throwable -> {
                    logger.atSevere().withCause(throwable).log("Error subscribing to %s", currencyPair);
                });
    }

    private void subscribeToTradeStreams() {
        currencyPairSupply.get().currencyPairs().stream()
            .forEach(pair -> {
                subscriptions.add(subscribeToTradeStream(pair));
            });
    }
}
