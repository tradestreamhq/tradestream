package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Observable;
import io.reactivex.rxjava3.disposables.Disposable;
import marketdata.Marketdata.Trade;

import java.util.ArrayList;
import java.util.List;
import java.util.Timer;

final class RealTimeDataIngestion implements MarketDataIngestion {
    private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;
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

    private void onTrade(Trade trade) {
        if (!tradeProcessor.isProcessed(trade)) {
            candleManager.processTrade(trade);
        }
    }

    private void startThinMarketTimer() {
        thinMarketTimer = new Timer();

    }

    private static class ThinMarketTimer {
        private final Timer timer;
        
        @Inject
        ThinMarketTimer(ThinMarketTimerTask timerTask) {
            this.timer = new Timer();
            this.timerTask = timerTask;
        }

        void start() {
            timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);            
        }
    }

    private static class ThinMarketTimerTask extends TimerTask {
        private final CandleManager candleManager;

        @Inject
        ThinMarketTimerTask(CandleManager candleManager) {
            this.candleManager = candleManager;
        }

        @Override
        public void run() {
            candleManager.handleThinlyTradedMarkets(currencyPairs);
        }
    }
}
