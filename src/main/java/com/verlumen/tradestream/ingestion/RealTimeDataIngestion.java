package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.disposables.Disposable;
import marketdata.Marketdata.Trade;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.*;

public class RealTimeDataIngestion {
    private final StreamingExchange exchange;
    private final StreamingMarketDataService marketDataService;
    private final List<String> currencyPairs;
    private final List<Disposable> subscriptions = new ArrayList<>();
    private final TradeProcessor tradeProcessor;
    private final CandleManager candleManager;
    private final CandlePublisher publisher;
    private Timer thinMarketTimer;

    @Inject
    public RealTimeDataIngestion(
            StreamingExchange exchange,
            StreamingMarketDataService marketDataService,
            List<String> currencyPairs,
            CandleManager candleManager,
            TradeProcessor tradeProcessor,
            CandlePublisher publisher) {
        this.exchange = exchange;
        this.marketDataService = marketDataService;
        this.currencyPairs = currencyPairs;
        this.candleManager = candleManager;
        this.tradeProcessor = tradeProcessor;
        this.publisher = publisher;
    }

    public void start() {
        exchange.connect().blockingAwait();
        subscribeToTradeStreams();
        startThinMarketTimer();
    }

    private void subscribeToTradeStreams() {
        for (String pair : currencyPairs) {
            CurrencyPair currencyPair = new CurrencyPair(pair);
            Disposable subscription = marketDataService.getTrades(currencyPair)
                    .subscribe(trade -> onTrade(convertTrade(trade, pair)));
            subscriptions.add(subscription);
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

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            candleManager.processTrade(trade);
        }
    }

    public void shutdown() {
        for (Disposable subscription : subscriptions) {
            subscription.dispose();
        }
        if (thinMarketTimer != null) {
            thinMarketTimer.cancel();
        }
        exchange.disconnect().blockingAwait();
        publisher.close();
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
}
