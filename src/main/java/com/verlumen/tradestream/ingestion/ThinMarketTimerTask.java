package com.verlumen.tradestream.ingestion;

import java.util.TimerTask;

/**
 * ThinMarketTimerTask defines a task to be executed during thin market conditions.
 * This can be used in conjunction with the ThinMarketTimer to perform specific actions,
 * such as forcing the generation of candles when there is little to no trading activity.
 */
abstract class AbstractThinMarketTimerTask extends TimerTask {}
