package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.disposables.Disposable;
import marketdata.Marketdata.Trade;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.ArrayList;
import java.util.List;
import java.util.Timer;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final CurrencyPairSupplier currencyPairSupplier;
    private final Provider<StreamingExchange> exchange;
    private final List<Disposable> subscriptions;
    private final ThinMarketTimer thinMarketTimer;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        CurrencyPairSupplier currencyPairSupplier,
        Provider<StreamingExchange> exchange,
        ThinMarketTimer thinMarketTimer,
        TradeProcessor tradeProcessor
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupplier = currencyPairSupplier;
        this.exchange = exchange;
        this.subscriptions = new ArrayList<>();
        this.thinMarketTimer = thinMarketTimer;
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {
        exchange.connect().blockingAwait();
        subscribeToTradeStreams();
        startThinMarketTimer();
    }

    @Override
    public void shutdown() {
        for (Disposable subscription : subscriptions) {
            subscription.dispose();
        }
        if (thinMarketTimer != null) {
            thinMarketTimer.cancel();
        }
        exchange.get().disconnect().blockingAwait();
        candlePublisher.close();
    }

    private Trade convertTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String pair) {
        return Trade.newBuilder()
            .setTimestamp(xchangeTrade.getTimestamp().getTime())
            .setExchange(exchange.getExchangeSpecification().getExchangeName())
            .setCurrencyPair(pair)
            .setPrice(xchangeTrade.getPrice().doubleValue())
            .setVolume(xchangeTrade.getOriginalAmount().doubleValue())
            .setTradeId(xchangeTrade.getId() != null ? xchangeTrade.getId() : UUID.randomUUID().toString())
            .build();
    }

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            candleManager.processTrade(trade);
        }
    }

    private void startThinMarketTimer() {
        thinMarketTimer = new Timer();
        thinMarketTimer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                candleManager.handleThinlyTradedMarkets(currencyPairs);
            }
        }, 0, 60000); // Every minute
    }

    private Observable<Trade> subscribeToTradeStream(String pair) {
        return exchange
            .getStreamingMarketDataService()
            .getTrades(new CurrencyPair(pair))
            .subscribe(trade -> onTrade(convertTrade(trade, pair)));
    }

    private void subscribeToTradeStreams() {
        for (String pair : currencyPairs) {
            CurrencyPair currencyPair = new CurrencyPair(pair);
            Disposable subscription = subscribeToTradeStream(pair);
            subscriptions.add(subscription);
        }
    }
}
