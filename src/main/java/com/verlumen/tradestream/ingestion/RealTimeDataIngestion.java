package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.marketdata.Trade;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.disposables.Disposable;

import java.util.ArrayList;
import java.util.List;
import java.util.Timer;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final CurrencyPairSupplier currencyPairSupplier;
    private final Provider<StreamingExchange> exchange;
    private final List<Disposable> subscriptions;
    private final TradeProcessor tradeProcessor;
    private Timer thinMarketTimer;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        CurrencyPairSupplier currencyPairSupplier,
        Provider<StreamingExchange> exchange,
        TradeProcessor tradeProcessor
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.currencyPairSupplier = currencyPairSupplier;
        this.exchange = exchange;
        this.subscriptions = new ArrayList<>();
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {
        exchange.get().connect().blockingAwait();
        subscribeToTradeStreams();
        // thinMarketTimer.start();
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
            .setExchange(exchange.get().getExchangeSpecification().getExchangeName())
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

    private void subscribeToTradeStream() {}

    private void subscribeToTradeStreams() {}
}
