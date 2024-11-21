package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.Timer;
import java.util.TimerTask;

final class ThinMarketTimer extends Timer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final Timer timer;
  private final TimerTask timerTask;
  private final AtomicBoolean isScheduled = new AtomicBoolean(false);

  @Inject
  ThinMarketTimerImpl(Timer timer, ThinMarketTimerTask timerTask) {
    this.timer = timer;
    this.timerTask = timerTask;
  }

  @Override
  public void start() {
    if (isScheduled.compareAndSet(false, true)) {
      timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);
    }
  }

  @Override
  public void cancel() {
    if (isScheduled.compareAndSet(true, false)) {
        timer.cancel();
    }
  }
}
