package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.Timer;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final ThinMarketTimerTask timerTask;
  private final Timer timer;

  @Inject
  ThinMarketTimerImpl(Timer timer, ThinMarketTimerTask timerTask) {
    this.timer = timer;
    this.timerTask = timerTask;
  }

  @Override
  public void start() {
    timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);            
  }

  @Override
  public void stop() {
    timer.cancel();
  }
}
