package com.verlumen.tradestream.ingestion;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final Timer timer;
  private final TimerTask timerTask;

  @Inject
  ThinMarketTimerImpl(CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
    this.timer = new Timer();
    this.timerTask = ThinMarketTimerTask.create(candleManager, currencyPairSupplier);
  }
   
  void start() {
      timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);            
  }
}

abstract static class ThinMarketTimerTask extends TimerTask {
    private static ThinMarketTimerTask create(CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
        return new AutoValue_RealTimeDataIngestion_ThinMarketTimerTask(candleManager, currencyPairSupplier);
    }

    abstract CandleManager candleManager();

    abstract CurrencyPairSuppier currencyPairSupplier();

    @Override
    public void run() {
        candleManager().handleThinlyTradedMarkets(currencyPairSupplier().currencyPairs());
    }
}
