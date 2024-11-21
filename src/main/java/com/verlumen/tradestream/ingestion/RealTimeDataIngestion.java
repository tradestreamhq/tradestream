package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.disposables.Disposable;

import java.util.List;
import java.util.Timer;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private final CandleManager candleManager;
    private final CandlePublisher candlePublisher;
    private final Provider<StreamingExchange> exchange;
    private final List<Disposable> subscriptions;
    private final TradeProcessor tradeProcessor;
    private Timer thinMarketTimer;
    
    @Inject
    RealTimeDataIngestion(
        CandleManager candleManager,
        CandlePublisher candlePublisher,
        Provider<StreamingExchange> exchange,
        TradeProcessor tradeProcessor
    ) {
        this.candleManager = candleManager;
        this.candlePublisher = candlePublisher;
        this.exchange = exchange;
        this.subscriptions =  = new ArrayList<>();
        this.tradeProcessor = tradeProcessor;
    }

    @Override
    public void start() {}

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
}
