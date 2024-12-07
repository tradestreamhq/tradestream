package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import org.knowm.xchange.currency.CurrencyPair;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.Timer;
import java.util.TimerTask;

final class ThinMarketTimerImpl implements ThinMarketTimer {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  private static final int ONE_MINUTE_IN_MILLISECONDS = 60_000;

  private final Timer timer;
  private final TimerTask timerTask;
  private final AtomicBoolean isScheduled = new AtomicBoolean(false);

  @Inject
  ThinMarketTimerImpl(Timer timer, ThinMarketTimerTask timerTask) {
    logger.atInfo().log("Initializing ThinMarketTimer");
    this.timer = timer;
    this.timerTask = timerTask;
    logger.atInfo().log("ThinMarketTimer initialization complete");
  }

  @Override
  public void start() {
    logger.atInfo().log("Attempting to start thin market timer...");
    if (!isScheduled.compareAndSet(false, true)) {
      logger.atInfo().log("Timer task already scheduled, ignoring start request");
      return;
    }

    logger.atInfo().log("Scheduling timer task with interval: %d ms", ONE_MINUTE_IN_MILLISECONDS);
    try {
      timer.scheduleAtFixedRate(timerTask, 0, ONE_MINUTE_IN_MILLISECONDS);
      logger.atInfo().log("Timer task scheduled successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Failed to schedule timer task");
      isScheduled.set(false);
      throw new RuntimeException("Failed to start thin market timer", e);
    }
  }

  @Override
  public void stop() {
    logger.atInfo().log("Attempting to stop thin market timer...");
    if (!isScheduled.compareAndSet(true, false)) {
      logger.atInfo().log("Timer was not running, ignoring stop request");
      return;
    }

    try {
        logger.atInfo().log("Cancelling timer...");
        timer.cancel();
        logger.atInfo().log("Timer cancelled successfully");
    } catch (Exception e) {
        throw new RuntimeException("Failed to stop thin market timer", e);
    }
  }
}
