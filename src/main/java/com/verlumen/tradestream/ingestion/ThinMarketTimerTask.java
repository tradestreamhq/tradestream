package com.verlumen.tradestream.ingestion;

import java.util.TimerTask;

/**
 * ThinMarketTimerTask defines a task to be executed during thin market conditions.
 * This can be used in conjunction with the ThinMarketTimer to perform specific actions,
 * such as forcing the generation of candles when there is little to no trading activity.
 */
abstract class ThinMarketTimerTask extends TimerTask {

  /**
   * Executes the task associated with thin market conditions.
   * This method is invoked by the ThinMarketTimer when a predefined interval elapses without significant market activity.
   */
  void execute();
}
