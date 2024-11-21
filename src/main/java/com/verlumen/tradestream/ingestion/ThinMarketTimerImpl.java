package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final ThinMarketTimerTask timerTask;
  private final Timer timer;

  @Inject
  ThinMarketTimerImpl(ThinMarketTimerTask timerTask, Timer timer) {
    this.timer = timer;
    this.timerTask = timerTask;
  }

  @Override
  public void start() {
    timer.scheduleAtFixedRate(task, 0, ONE_MINUTE_IN_MILLISECONDS);            
  }

  @Override
  public void stop() {
    timer.cancel();
  }
}
