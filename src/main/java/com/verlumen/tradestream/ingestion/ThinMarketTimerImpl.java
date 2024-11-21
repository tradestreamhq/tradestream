package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final Timer timer;
  private final ThinMarketTimerTask timerTask;

  @Inject
  ThinMarketTimerImpl(CandleManager candleManager, ThinMarketTimerTask timerTask) {
    this.timer = new Timer();
    this.timerTask = thinMarketTimerTask;
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
