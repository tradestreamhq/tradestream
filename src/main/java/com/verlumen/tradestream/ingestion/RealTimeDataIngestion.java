package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.marketdata.Trade;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.disposables.Disposable;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.ArrayList;
import java.util.List;
import java.util.Timer;
import java.util.UUID;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final CurrencyPairSupplier currencyPairSupplier;
    private final Provider<StreamingExchange> exchange;
    private final List<Disposable> subscriptions;
    private final Provider<ThinMarketTimer> thinMarketTimer;
    private final TradeProcessor tradeProcessor;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        CurrencyPairSupplier currencyPairSupplier,
        Provider<StreamingExchange> exchange,
        Provider<ThinMarketTimer> thinMarketTimer,
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
        exchange.get().connect().blockingAwait();
        subscribeToTradeStreams();
        thinMarketTimer.get().start();
    }

    @Override
    public void shutdown() {
        subscriptions.forEach(Disposable::dispose);
        thinMarketTimer.get().stop();
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

    private void handleTrade(org.knowm.xchange.dto.marketdata.Trade xchangeTrade, String currencyPair) {
        String symbol = currencyPair.toString();
        Trade trade = convertTrade(xchangeTrade, symbol);
        onTrade(trade);
    }

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            candleManager.processTrade(trade);
        }
    }

    private Disposable subscribeToTradeStream(CurrencyPair currencyPair) {
        return exchange
            .get()
            .getStreamingMarketDataService()
            .getTrades(currencyPair)
            .subscribe(trade -> handleTrade(trade, currencyPair.toString()));
    }

    private void subscribeToTradeStreams() {
        currencyPairSupplier
            .currencyPairs()
            .stream()
            .map(this::subscribeToTradeStream)
            .forEach(subscriptions::add);
    }
}
