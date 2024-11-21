package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;
import java.util.Timer;
import java.util.TimerTask;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final Timer timer;
  private final TimerTask timerTask;

  @Inject
  ThinMarketTimerImpl(CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
    this.timer = new Timer();
    this.timerTask = ThinMarketTimerTask.create(candleManager, currencyPairSupplier);
  }

  @Override
  public void start() {
    timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);            
  }

  @Override
  public void stop() {
    timer.cancel();
  }

  @AutoValue
  abstract static class ThinMarketTimerTask extends TimerTask {
      static ThinMarketTimerTask create(CandleManager candleManager, CurrencyPairSupplier currencyPairSupplier) {
          return new AutoValue_RealTimeDataIngestion_ThinMarketTimerTask(candleManager, currencyPairSupplier);
      }
  
      abstract CandleManager candleManager();
  
      abstract CurrencyPairSupplier currencyPairSupplier();
  
      @Override
      public void run() {
          ImmutableList<String> currencyPairs =
            currencyPairSupplier()
            .currencyPairs()
            .stream()
            .map(Object::toString)
            .collect(toImmutableList());
          candleManager().handleThinlyTradedMarkets(currencyPairs);
      }
  }
}
